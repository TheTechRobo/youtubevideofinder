const getDataDiv = () => document.getElementById("data");
const getVideoInput = () => document.getElementById("videoInput");
const getSubmitBtn = () => document.getElementById("submit");

function isValidVideoId(videoId) {
    return videoId.match(/^[A-Za-z0-9_-]{10}[AEIMQUYcgkosw048]$/)
}

function getVideoId(videoInput) {
    // Regexes here are based on the ones from https://github.com/mattwright324/youtube-metadata/blob/master/js/shared.js#L8-L14
    let patterns = [
        /(?:https?:\/\/)?(?:\w+\.)?youtube\.com\/watch\/?\?v=([A-Za-z0-9_-]{10}[AEIMQUYcgkosw048])(?:[\/&].*)?/i,
        /(?:https?:\/\/)?(?:\w+\.)?youtube.com\/(?:v|embed|shorts|video)\/([A-Za-z0-9_-]{10}[AEIMQUYcgkosw048])(?:[\/&].*)?/i,
        /(?:https?:\/\/)?youtu.be\/([A-Za-z0-9_-]{10}[AEIMQUYcgkosw048])(?:\?.*)?/i,
        /(?:https?:\/\/)?filmot.com\/video\/([A-Za-z0-9_-]{10}[AEIMQUYcgkosw048])(?:\?.*)?/i,
    ]
    for (i = 0; i < patterns.length; i++) {
        let pattern = patterns[i];
        let newVid = videoInput.replace(pattern, function (match, newVid) {
            return newVid;
        });
        if (isValidVideoId(newVid)) {
            return newVid;
        }
    }
    return false;
}

function makeServiceEntry(result) {
    var colour;
    if (result.error) {
        colour = "white";
    } else if (result.archived && result.metaonly) {
        colour = "yellow";
    } else if (result.archived) {
        colour = "green";
    } else {
        colour = "red";
    }
    var isarchived = result.archived ? "Available" : "Not Available";
    if (result.error !== null) {
        isarchived = "Unknown";
        result.note = result.note + result.error;
    }

    let archived = `<span class='${colour}'>${isarchived}</span>`;
    let metaonly = (result.metaonly && result.archived) ? " (metadata only) " : " ";
    let comments = (result.archived && result.comments) ? " (incl. comments) " : " ";
    let lien = result.available ? `<a href="${result.available}">(link)</a>` : ""
    return `${archived}${metaonly}${comments}${lien}<br />${result.note}`
}

// https://stackoverflow.com/a/48054293/9654083
function escapeHTML(unsafeText) {
    let div = document.createElement('div');
    div.innerText = unsafeText;
    return div.innerHTML;
}

function makeLoadingElement(title) {
    const li = document.createElement("li");
    li.innerHTML = `
        <b>${escapeHTML(title)}</b>:
        <span class="result"><img src="/static/loading.gif" style="height: 1em;" /> Loading...</span>
    `;
    li.setAttribute("data-status", "loading");
    return li;
}

function finish(vid1) {
    const dataDiv = getDataDiv()
    const submitBtn = getSubmitBtn()
    const videoInput = getVideoInput()

    plausible('FormSubmit')
    var vid = vid1;
    if (!isValidVideoId(vid)) {
        let newVid = getVideoId(vid);
        console.log(newVid);
        if (!newVid) {
            dataDiv.innerHTML = `<span style="color:red;">That doesn't look like a valid video ID.<br />If it is valid, please report the bug on github!</span>`;
            submitBtn.disabled = false;
            submitBtn.innerHTML = "Search for Captures";
            return false;
        }
        dataDiv.innerHTML = `<br>Interpreting that URL as video ID ${newVid}`;
        videoInput.value = vid1;
        vid = newVid;
    }

    // https://www.behance.net/gallery/31234507/Open-source-Loading-GIF-Icons-Vol-1
    dataDiv.innerHTML += `<div style="display: flex; gap: 12px;"><img src="/static/loading.gif" width="25" height="25" /> Loading could take up to 30 seconds.</div>`;
    fetch(`api/v4/youtube/${vid}?stream`)
        .then((response) => {
            if (response.status === 410 || response.status === 404) {
                dataDiv.innerHTML = `<span style="color: red;">API version is not supported - this should never happen</span>`;
                return null;
            }
            if (response.status === 500) {
                dataDiv.innerHTML = `<span style="color: red;">Internal server error - this is not your fault, please try again</span>`;
                return null;
            }
            if (response.status === 429) {
                dataDiv.innerHTML = `<span style="color: red;">You have been rate limited - please slow down</span>`;
                return null;
            }
            return response.body.getReader();
        })
        .then((stream) => {
            if (stream === null) {
                return;
            }
            const possible_states = Object.freeze({
                Preparation: "Preparation",
                Generation: "Generation",
                Verdict: "Verdict"
            });
            let ul = document.createElement("ul");
            dataDiv.innerHTML = "";
            dataDiv.appendChild(ul);
            let state = possible_states.Preparation;
            let currentline = "";
            let elements = {};
            function processLine(line) {
                if (line === "" || line === "\n") {
                    return;
                }
                let data = JSON.parse(line);
                switch(state) {
                    case possible_states.Preparation: {
                        for (const [key, value] of Object.entries(data)) {
                            elements[key] = makeLoadingElement(value);
                            ul.appendChild(elements[key]);
                        }
                        state = possible_states.Generation;
                        break;
                    }
                    case possible_states.Generation: {
                        if (data === null) {
                            state = possible_states.Verdict;
                            return;
                        }
                        const cln = data.classname;
                        elements[cln].querySelector(".result").innerHTML = makeServiceEntry(data);
                        elements[cln].setAttribute("data-status", "done");
                        break;
                    }
                    case possible_states.Verdict: {
                        return;
                    }
                    default: {
                        throw new Error("unexpected state")
                    }
                }
            }
            function pump() {
                return stream.read().then(({ done, value }) => {
                    if (done) {
                        return;
                    }
                    let text = new TextDecoder().decode(value);
                    for (const c of text) {
                        currentline += c
                        if (c === "\n") {
                            processLine(currentline);
                            currentline = "";
                        }
                    }
                    return pump();
                }).catch((e) => {
                    console.log(`! CONNECTION ERROR ! (${e})`);
                    Object.values(elements).forEach((i) => {
                        if (i.getAttribute("data-status") == "loading") {
                            i.querySelector(".result").innerHTML = '<span class="white">Error</span><br />A connection error occured while receiving data. Please try again; if it persists, contact me (details are at the bottom of "How do I use this?") and provide console output and a way to reproduce if possible.';
                        }
                    });
                });
            }
            return pump();
        })
        .catch((e) => {
            dataDiv.innerHTML = '<span class="red" style="background-color: #fff;">An error occurred, check your internet connection</span>';
            throw (e);
        })
        .finally(() => {
            submitBtn.disabled = false;
            submitBtn.innerHTML = "Search for Captures";
        });
}

function finishWrpa(data) {
    const dataDiv = getDataDiv()
    const submitBtn = getSubmitBtn()

    submitBtn.disabled = true;
    submitBtn.innerHTML = "Searching...";
    try {
        return finish(data);
    } catch (err) {
        console.error(err)
        dataDiv.innerHTML = "<span class='red'>An unknown error occured. Please report this. If possible, provide console output and a way of reproducing.</span>";
    }
}
