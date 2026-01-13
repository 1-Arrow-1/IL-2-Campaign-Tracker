let cropper, pilotMap = {}, currentDesc = "";

// ----------- Game Path Modal Logic -----------
const gamePathModal = document.getElementById('gamePathModal');
const gamePathInput = document.getElementById('gamePathInput');
const gamePathError = document.getElementById('gamePathError');
const gamePathSubmit = document.getElementById('gamePathSubmit');
const serviceRecord = document.getElementById('service-record-page');
const statsPage = document.getElementById('stats-page');
const logbookPage = document.getElementById('logbook-page');
const arrowNext = document.getElementById('arrow-next');
const arrowPrev = document.getElementById('arrow-prev');
const pilotSelect = document.getElementById('pilot-select');


function showGamePathModal(defaultError = "") {
    gamePathInput.value = localStorage.getItem('il2GamePath') || "";
    gamePathError.textContent = defaultError;
    gamePathModal.style.display = "flex";
    setTimeout(()=>gamePathInput.focus(), 10);
    document.body.style.pointerEvents = "none";
    gamePathModal.style.pointerEvents = "auto";
}
function hideGamePathModal() {
    gamePathModal.style.display = "none";
    document.body.style.pointerEvents = "";
}

gamePathSubmit.onclick = function() {
    const path = gamePathInput.value.trim();
    if (!path) {
        gamePathError.textContent = "Please enter the game folder path.";
        return;
    }
    setGamePath(path);
};
gamePathInput.addEventListener('keydown', function(e){
    if (e.key === 'Enter') gamePathSubmit.onclick();
});

function setGamePath(path) {
    fetch('/api/set_game_path', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({game_path: path})
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) {
            localStorage.setItem('il2GamePath', path);
            hideGamePathModal();
            fetchPilots();
        } else {
            localStorage.removeItem('il2GamePath');
            gamePathError.textContent = (data.error || "Unknown error. Please check your folder.");
            clearPassportUI();
        }
    })
    .catch(() => {
        gamePathError.textContent = "Could not connect to backend.";
        clearPassportUI();
    });
}

// ----------- Pilot Logic -----------
function fetchPilots() {
  console.log("fetchPilots: stored path is", localStorage.getItem('il2GamePath'));
  const sel = document.getElementById('pilot-select');
  sel.innerHTML = "<option>Loading...</option>";
  pilotMap = {};

  fetch("/api/pilots")
    .then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then(data => {
      console.log("fetchPilots result:", data);

      if (!Array.isArray(data)) {
        console.log("fetchPilots: bad shape, not an array:", data);
        // Don't drop the path; just inform the user of unexpected backend output.
        showGamePathModal("Unexpected response from backend. Please verify your IL-2 folder.");
        clearPassportUI();
        return;
      }

      if (data.length === 0) {
        console.log("fetchPilots: empty pilots array for path", localStorage.getItem('il2GamePath'));
        // Valid path, but no pilots. Prompt without clearing path.
        showGamePathModal("No pilots found in that installation. Verify the folder contains valid pilot data.");
        clearPassportUI();
        return;
      }

      // Success: keep the path, populate list
      hideGamePathModal();
      sel.innerHTML = "";
      pilotMap = {};
      data.forEach((p, i) => {
        const label = `${p.display || "Unknown"} - ${p.country || ""} - ${p.squadron || ""}`;
        sel.innerHTML += `<option value="${encodeURIComponent(p.desc)}">${label}</option>`;
        pilotMap[encodeURIComponent(p.desc)] = p.desc;
      });
      sel.selectedIndex = 0;
      loadPilot();
      showPage(0);
    })
    .catch((e) => {
      console.error("fetchPilots failed:", e);
      // Only drop stored path on real fetch failure (connectivity / server unreachable)
      localStorage.removeItem('il2GamePath');
      showGamePathModal("Unable to connect to server or no valid game path.");
      clearPassportUI();
    });
}


function clearPassportUI() {
  // Set all fields to empty or placeholder image
  document.getElementById('pilot-firstname').textContent = "";
  document.getElementById('pilot-lastname').textContent = "";
  document.getElementById('pilot-dob').textContent = "";
  document.getElementById('pilot-pob').textContent = "";
  document.getElementById('pilot-id').textContent = "";
  document.getElementById('pilot-sq').textContent = "";
  document.getElementById('pilot-rank').textContent = "";
  document.getElementById('pilot-photo').src = "static/images/sample_photo.jpg";
  document.getElementById('promotion-list').innerHTML = '';
  document.getElementById('award-list').innerHTML = '';
  document.getElementById('stats-table').innerHTML = '';
}

// Only fetch once (no duplicate /service_record fetch)
function loadPilot() {
  let sel = document.getElementById('pilot-select');
  let desc_encoded = sel.value;
  let desc = pilotMap[desc_encoded];
  currentDesc = desc;
  if (!desc) { clearPassportUI(); return; }
  fetch('/api/service_record?desc=' + encodeURIComponent(desc))
    .then(r => r.json())
    .then(updatePassport)
    .catch(()=>clearPassportUI());
  // Reset UI to record page
  serviceRecord.style.display = "";
  statsPage.style.display = "none";
  arrowNext.style.display = "";
  arrowPrev.style.display = "none";
}
document.getElementById('pilot-select').addEventListener('change', loadPilot);

function updatePassport(data) {
  let info = (data && data.pilot_info) || {};
  document.getElementById('pilot-firstname').textContent = info.first_name || "";
  document.getElementById('pilot-lastname').textContent = info.last_name || "";
  document.getElementById('pilot-dob').textContent = info.birth_date || '';
  document.getElementById('pilot-pob').textContent = info.birth_country || '';
  document.getElementById('pilot-id').textContent = info.pilot_id || '';
  document.getElementById('pilot-sq').textContent = info.squadron || '';
  document.getElementById('pilot-rank').textContent = info.rank_name || '';
  // Show photo (with fallback)
  document.getElementById('pilot-photo').src = (info.photo_url ? (info.photo_url + "?t=" + Date.now()) : "static/images/sample_photo.jpg");

  // Promotions
  let promolist = document.getElementById('promotion-list');
  promolist.innerHTML = '';
  (data.promotions || []).forEach(p => {
    let imgTag = p.img ? `<img src="${p.img}" alt="Rank" class="rank-icon" style="margin-right:5px;">` : '';
    promolist.innerHTML += `<li>${imgTag}<span>${p.desc}</span><span>${p.date}</span></li>`;
  });
  document.getElementById('promotion-watermark').style.display = ((data.promotions || []).length > 0) ? '' : 'none';

  // Awards
  let awardlist = document.getElementById('award-list');
  awardlist.innerHTML = '';
  (data.awards || []).forEach(a => {
    let imgPath = `/static/achievements/${a.tpar2}/preview.png`;
    awardlist.innerHTML += `<li>
        <img src="${imgPath}" alt="Medal" class="award-icon" onerror="this.src='static/images/award_placeholder.png'">
        <span>${a.desc}</span>
        <span>${a.date}</span>
      </li>`;
  });
}

function changePhoto() {
  let input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/*';
  input.onchange = e => {
    let file = e.target.files[0];
    if (!file) return;
    let reader = new FileReader();
    reader.onload = evt => {
      let modal = document.getElementById('cropper-modal');
      let img = document.getElementById('cropper-img');
      img.src = evt.target.result;
      modal.style.display = 'block';
      if (cropper) cropper.destroy();
      img.onload = function() {
        cropper = new Cropper(img, {
          aspectRatio: 180/220,
          viewMode: 1,
          autoCropArea: 1,
          background: false,
          movable: true,
          zoomable: true,
          rotatable: false,
          scalable: false,
          minCropBoxWidth: 90,
          minCropBoxHeight: 110,
        });
      }
    };
    reader.readAsDataURL(file);
  };
  input.click();
}

function cancelCrop() {
  if (cropper) { cropper.destroy(); cropper = null; }
  document.getElementById('cropper-modal').style.display = 'none';
}

function doCrop() {
  if (!cropper) return;
  let canvas = cropper.getCroppedCanvas({width:180, height:220});
  let imgData = canvas.toDataURL("image/png");
  if (currentDesc) {
    fetch('/api/save_photo', {
      method: 'POST',
      body: new URLSearchParams({desc: currentDesc, img_data: imgData}),
    })
    .then(r => r.json())
    .then(data => {
      if(data.path) {
        document.getElementById('pilot-photo').src = data.path + "?t=" + Date.now();
      }
      cancelCrop();
    });
  } else {
    document.getElementById('pilot-photo').src = imgData;
    cancelCrop();
  }
}

let currentPage = 0;
function showPage(idx) {
  // guard in case bindings failed
  if (!serviceRecord || !statsPage || !logbookPage || !arrowNext || !arrowPrev) {
    console.warn("showPage called but some UI elements are missing", { idx });
    return;
  }

  serviceRecord.style.display = idx === 0 ? "" : "none";
  statsPage.style.display = idx === 1 ? "" : "none";
  logbookPage.style.display = idx === 2 ? "" : "none";

  arrowPrev.style.display = idx > 0 ? "" : "none";
  arrowNext.style.display = idx < 2 ? "" : "none";

  currentPage = idx;

  if (idx === 1) loadStats(currentDesc);
  if (idx === 2) loadLogbook(currentDesc);
}
arrowNext.onclick = () => showPage(currentPage + 1);
arrowPrev.onclick = () => showPage(currentPage - 1);



function loadStats(desc) {
  if (!desc) return;
  fetch('/api/pilot_stats?desc=' + encodeURIComponent(desc))
    .then(r => r.json())
    .then(data => {
      const tbl = document.getElementById('stats-table');
      tbl.innerHTML = '';
      Object.entries(data).forEach(([k, value]) => {
		  let display = value;
		  if (k.toLowerCase().includes('flight time') && typeof value === 'number') {
			const seconds = value;
			const hours = Math.floor(seconds / 3600);
			const minutes = Math.floor((seconds % 3600) / 60);
			display = `${hours} h ${minutes} min`;
		  }
		  const tbl = document.getElementById('stats-table');
		  tbl.innerHTML += `<div class="stats-row"><span class="stats-label">${k}:</span><span class="stats-value">${display}</span></div>`;
		});
    });
}

function formatSingleKill(value) {
  return value ? value : "";
}

function loadLogbook(desc) {
  if (!desc) return;
  fetch('/api/pilot_sorties?desc=' + encodeURIComponent(desc))
    .then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then(data => {
      const tableDiv = document.getElementById('logbook-table');
      if (!Array.isArray(data) || data.length === 0) {
        tableDiv.innerHTML = "<div style='margin-top:30px;'>No sorties found for this pilot.</div>";
        return;
      }

      // Build HTML table with stacked headers and separate kill columns
        let html = `
      <table class="logbook-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Aircraft</th>
            <th>Mission</th>
            <th>
              <div class="stacked-header">
                <img src="static/images/killplanetargets.png" alt="Air kills" title="Air kills" class="header-icon">
              </div>
            </th>
            <th>
              <div class="stacked-header">
                <img src="static/images/killvehicletargets.png" alt="Vehicle kills" title="Vehicle kills" class="header-icon">
              </div>
            </th>
            <th>
              <div class="stacked-header">
                <img src="static/images/killboattargets.png" alt="Naval kills" title="Naval kills" class="header-icon">
              </div>
            </th>
            <th>
              <div class="stacked-header">
                <img src="static/images/killartillerytargets.png" alt="Artillery kills" title="Artillery kills" class="header-icon">
              </div>
            </th>
            <th>
              <div class="stacked-header">
                <img src="static/images/killrailroadtargets.png" alt="Railway kills" title="Railway kills" class="header-icon">
              </div>
            </th>
            <th>
              <div class="stacked-header">
                <img src="static/images/killstructuretargets.png" alt="Structure kills" title="Structure kills" class="header-icon">
              </div>
            </th>
            <th>
              <div class="stacked-header">
                <img src="static/images/flighttime.png" alt="Flight time" title="Flight time" class="header-icon">
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
    `;

     data.forEach(sortie => {
       html += `
        <tr>
          <td>${sortie.date || ''}</td>
          <td>${sortie.aircraft || ''}</td>
          <td>${sortie.mission_type || ''}</td>
          <td>${sortie.air_kills || ''}</td>
          <td>${sortie.ground_kills || ''}</td>
          <td>${sortie.naval_kills || ''}</td>
          <td>${sortie.artillery_kills || ''}</td>
          <td>${sortie.railway_kills || ''}</td>
          <td>${sortie.structure_kills || ''}</td>
          <td>${sortie.flight_time || ''}</td>
        </tr>
      `;
     });

      html += "</tbody></table>";
      tableDiv.innerHTML = html;
    })
    .catch(e => {
      console.error("loadLogbook error:", e);
      document.getElementById('logbook-table').innerHTML = "Failed to load logbook.";
    });
}

function humanizeMissionType(raw) {
  if (!raw) return "";
  return raw
    .split(' ')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}




function formatFlightTime(seconds) {
  if (!seconds) return '';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${minutes}m`;
}



window.addEventListener('DOMContentLoaded', function() {
    const lastPath = localStorage.getItem('il2GamePath');
    if (lastPath) {
        // Optimistically use existing path to load pilots without immediately nuking it if validation is flaky.
        fetchPilots();

        // In background, validate the path; only show modal if validation definitively fails.
        fetch('/api/set_game_path', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({game_path: lastPath})
        })
        .then(r => r.json())
        .then(data => {
            if (data.ok) {
                // keep it, nothing else needed
                hideGamePathModal();
            } else {
                // backend rejected path: clear and prompt user
                localStorage.removeItem('il2GamePath');
                showGamePathModal("Stored game path is no longer valid. Please re-enter.");
                clearPassportUI();
            }
        })
        .catch(() => {
            // validation failed (network glitch), but don't throw away path—just warn lightly if you want.
            console.warn("Background game path validation failed; retaining existing path.");
        });
    } else {
        showGamePathModal(); // force user to supply path
    }
});



setInterval(() => {
    fetch('/api/ping', {method: 'POST'});
}, 5000); // Sends a ping every 5 seconds