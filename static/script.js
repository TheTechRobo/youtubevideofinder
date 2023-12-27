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
    fetch(`api/v4/youtube/${vid}`)
        .then((response) => {
            if (response.status === 410 || response.status === 404) {
                dataDiv.innerHTML = `<span style="color: red;">API version is not supported - this should never happen</span>`;
                return null;
            }
            if (response.status === 500) {
                dataDiv.innerHTML = `<span style="color: red;">Internal server error - this is not your fault, please try again</span>`;
                return null;
            }
            return response.json();
        })
        .then((data) => {
            if (data === null) {
                return;
            }
            let write = "<ul>";
            let keys = data.keys;
            keys.forEach((wbm) => {
                var colour;
                if (wbm.error) {
                    colour = "white";
                } else if (wbm.archived && wbm.metaonly) {
                    colour = "yellow";
                } else if (wbm.archived) {
                    colour = "green";
                } else {
                    colour = "red";
                }
                var isarchived = wbm.archived ? "Available" : "Not Available";
                if (wbm.error !== null) {
                    isarchived = "Unknown";
                    wbm.note = wbm.note + wbm.error;
                }
                let archived = `<span class='${colour}'>${isarchived}</span>`;
                let metaonly = (wbm.metaonly && wbm.archived) ? " (metadata only) " : " ";
                let comments = (wbm.archived && wbm.comments) ? " (incl. comments) " : " ";
                let lien = wbm.available ? `<a href="${wbm.available}">(link)</a>` : ""
                write += `<li><b>${wbm.name}:</b> ${archived}${metaonly}${comments}${lien}<br>`
                write += `${wbm.note}</li>`;

            });
            let elm = document.getElementById("data");
            elm.innerHTML = write;
            submitBtn.innerHTML = "Search for Captures";
        })
        .catch((e) => {
            dataDiv.innerHTML = '<span class="red" style="background-color: #FFFFFF;">An error occurred, check your internet connection</span>';
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
        dataDiv.innerHTML = "<span class='red'>This should be unreachable. Please report this issue and provide a way to reproduce.</span>";
    }
}
