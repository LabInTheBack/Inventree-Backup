/* Recording is isolated from finder selection, search and hardware actions. */
(() => {
  "use strict";
  const config = JSON.parse(document.getElementById("finder-config").textContent);
  const find = (name) => document.querySelector(`[data-voice-${name}]`);
  const input = document.getElementById("part-queries");
  const transcript = document.getElementById("voice-transcript");
  const queries = document.getElementById("voice-queries");
  const interpreterReady = typeof config.interpret_url === "string" && config.interpreter_version === 3;
  const csrfToken = document.querySelector("[data-search-form]").elements.csrfmiddlewaretoken.value;
  const maxSeconds = config.max_recording_seconds;
  const maxBytes = config.max_audio_bytes;
  let phase = "idle";
  let generation = 0;
  let stream = null;
  let recorder = null;
  let timer = null;
  let controller = null;
  let retryAudio = null;
  let started = 0;
  let supported = false;
  let draftReady = false;
  let interpretationController = null;
  let stageTimer = null;
  let stageStarted = 0;
  let activeStage = null;

  function showReview() {
    find("workspace").hidden = false;
    find("workspace").open = true;
    find("review").hidden = false;
  }

  function stageNode(stage) {
    return find(stage === "transcribing" ? "transcription-time" : "interpretation-time");
  }

  function startStage(stage) {
    clearInterval(stageTimer);
    activeStage = stage;
    stageStarted = performance.now();
    const node = stageNode(stage);
    node.hidden = false;
    const tick = () => {
      node.textContent = `${stage === "transcribing" ? "Transcribing" : "Interpreting"} · ${((performance.now() - stageStarted) / 1000).toFixed(1)} s`;
    };
    tick();
    stageTimer = setInterval(tick, 250);
  }

  function finishStage(stage, label) {
    if (activeStage !== stage) return;
    clearInterval(stageTimer);
    stageTimer = null;
    stageNode(stage).textContent = `${label} · ${((performance.now() - stageStarted) / 1000).toFixed(1)} s`;
    activeStage = null;
  }

  function resetTimings() {
    clearInterval(stageTimer);
    stageTimer = null;
    activeStage = null;
    for (const stage of ["transcribing", "interpreting"]) {
      stageNode(stage).hidden = true;
      stageNode(stage).textContent = "";
    }
  }

  function queryLines(value) {
    return value.split(/[\n;]+/u).map((line) => line.trim().replace(/\s+/gu, " ")).filter(Boolean);
  }

  function validLines(lines) {
    return lines.length > 0 && lines.length <= config.max_queries
      && lines.every((line) => line.length <= config.max_query_length && line.split(" ").length <= config.max_query_terms);
  }

  function draftMessage(text, error = false) {
    find("query-status").textContent = text;
    find("query-status").classList.toggle("error", error);
  }

  function message(text, error = false) {
    find("status").textContent = text;
    find("status").classList.toggle("error", error);
  }

  function controls() {
    const busy = phase !== "idle";
    find("region").setAttribute("aria-busy", String(busy));
    find("record").disabled = !supported || busy;
    find("paste").disabled = busy || !interpreterReady;
    find("interpret").disabled = busy || !interpreterReady || !transcript.value.trim();
    find("stop").hidden = phase !== "recording";
    find("cancel").hidden = !busy;
    find("cancel").textContent = ["transcribing", "interpreting"].includes(phase) ? "Cancel request" : "Discard recording";
    find("retry").hidden = !retryAudio || busy;
    find("timer").hidden = phase !== "recording";
    transcript.readOnly = busy;
    queries.readOnly = busy;
    find("use").disabled = busy || !draftReady || !validLines(queryLines(queries.value)) || input.disabled;
  }

  function releaseMicrophone() {
    clearInterval(timer);
    timer = null;
    if (stream) stream.getTracks().forEach((track) => track.stop());
    stream = null;
  }

  function discard() {
    generation += 1;
    if (recorder?.state === "recording") recorder.stop();
    recorder = null;
    releaseMicrophone();
    controller?.abort();
    interpretationController?.abort();
    controller = null;
    interpretationController = null;
    retryAudio = null;
    if (activeStage) finishStage(activeStage, "Cancelled");
    phase = "idle";
    controls();
  }

  async function interpret(current) {
    if (!interpreterReady || !transcript.value.trim()) return;
    phase = "interpreting";
    startStage("interpreting");
    draftReady = false;
    queries.value = "";
    find("query-review").hidden = false;
    find("notes").replaceChildren();
    draftMessage("Preparing search lines…");
    message("Interpreting the request…");
    controls();
    const activeRequest = new AbortController();
    interpretationController = activeRequest;
    const timeout = setTimeout(() => activeRequest.abort(), 40000);
    try {
      const response = await fetch(config.interpret_url, {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: {"Content-Type": "application/json", "X-CSRFToken": csrfToken},
        body: JSON.stringify({text: transcript.value}),
        signal: activeRequest.signal,
      });
      const payload = await response.json().catch(() => ({}));
      if (current !== generation) return;
      if (response.status === 401 || response.status === 403) {
        throw new Error("Your session or request token has expired. Reload and sign in again.");
      }
      if (!response.ok || payload.success !== true) {
        throw new Error(payload.error || "Could not interpret the request. Retry or enter short search lines manually.");
      }
      if (payload.version !== config.interpreter_version) {
        throw new Error("The voice interpreter version is outdated. Restart InvenTree and refresh this page before retrying.");
      }
      if (!Array.isArray(payload.requests) || !payload.requests.length || payload.requests.length > config.max_queries
          || payload.requests.some((item) => !item || typeof item !== "object" || typeof item.query !== "string" || item.query.length > 8192
            || !Array.isArray(item.warnings) || !Array.isArray(item.notes) || typeof item.needs_edit !== "boolean"
            || [...item.warnings, ...item.notes].some((note) => typeof note !== "string"))) {
        throw new Error("The request interpretation was incomplete. Retry or edit the search lines manually.");
      }
      const prepared = payload.requests.map((item) => item.query).join("\n");
      if (prepared.length > 8192) throw new Error("The interpretation is too long. Shorten the request.");
      queries.value = prepared;
      if (typeof payload.notice === "string" && payload.notice) {
        const notice = document.createElement("li");
        notice.className = "warning";
        notice.textContent = payload.notice;
        find("notes").append(notice);
      }
      for (const [index, item] of payload.requests.entries()) {
        for (const [kind, notes] of [["warning", item.warnings], ["note", item.notes]]) {
          for (const note of notes) {
            const line = document.createElement("li");
            line.className = kind;
            line.textContent = `${index + 1}: ${note}`;
            find("notes").append(line);
          }
        }
      }
      draftReady = payload.requests.every((item) => !item.needs_edit);
      draftMessage(!draftReady
        ? "Some requests need correction. Edit the transcript and interpret again, or edit the search lines before adding."
        : validLines(queryLines(prepared))
        ? `${payload.requests.length} search line${payload.requests.length === 1 ? "" : "s"} prepared. Review the lines and notes before adding.`
        : `Shorten each line to ${config.max_query_length} characters and ${config.max_query_terms} words before adding.`,
      !draftReady || !validLines(queryLines(prepared)));
      message(draftReady ? `Search lines ready for review${payload.interpreter === "ollama" ? " using the local model" : ""}. Nothing has been searched or selected.`
        : "Review the flagged requests before adding them to search.", !draftReady);
      finishStage("interpreting", "Interpreted");
    } catch (error) {
      if (current !== generation) return;
      finishStage("interpreting", "Interpretation failed");
      draftMessage(error.name === "AbortError" ? "Interpretation timed out. Retry or edit the search lines manually." : error.message, true);
      message("The transcript is available. Retry interpretation or enter short search lines manually.", true);
    } finally {
      clearTimeout(timeout);
      if (current === generation) {
        interpretationController = null;
        phase = "idle";
        controls();
      }
    }
  }

  async function upload(audio, current) {
    phase = "transcribing";
    resetTimings();
    startStage("transcribing");
    retryAudio = null;
    message("Transcribing… The first request may take longer while Whisper loads.");
    controls();
    const activeRequest = new AbortController();
    controller = activeRequest;
    const timeout = setTimeout(() => activeRequest.abort(), 70000);
    try {
      const response = await fetch(config.transcribe_url, {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: {"Content-Type": audio.type, "X-CSRFToken": csrfToken},
        body: audio, signal: activeRequest.signal,
      });
      const payload = await response.json().catch(() => ({}));
      if (current !== generation) return;
      if (response.status === 401 || response.status === 403) {
        throw new Error("Your session or request token has expired. Reload and sign in again.");
      }
      if (!response.ok || payload.success !== true) {
        throw new Error(payload.error || "Transcription failed. Check the connection and try again.");
      }
      if (typeof payload.text !== "string" || !payload.text.trim() || payload.text.length > 8192) {
        throw new Error("The speech service returned an invalid transcript.");
      }
      transcript.value = payload.text;
      showReview();
      finishStage("transcribing", "Transcribed");
      clearTimeout(timeout);
      await interpret(current);
    } catch (error) {
      if (current !== generation) return;
      finishStage("transcribing", "Transcription failed");
      retryAudio = audio;
      message(error.name === "AbortError"
        ? "Transcription timed out. You can retry or record a shorter request."
        : error.message || "Cannot reach InvenTree. Check the connection and retry.", true);
    } finally {
      clearTimeout(timeout);
      if (current === generation) {
        controller = null;
        phase = "idle";
        controls();
      }
    }
  }

  async function record() {
    if (phase !== "idle" || !supported) return;
    const current = ++generation;
    phase = "permission";
    resetTimings();
    retryAudio = null;
    message("Waiting for microphone permission…");
    controls();
    try {
      const acquired = await navigator.mediaDevices.getUserMedia({audio: true});
      if (current !== generation) {
        acquired.getTracks().forEach((track) => track.stop());
        return;
      }
      stream = acquired;
      const mimeType = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4"]
        .find((type) => MediaRecorder.isTypeSupported(type));
      if (!mimeType) throw new Error("This browser cannot record a supported audio format. Try a current Chrome, Firefox or Safari.");
      const active = new MediaRecorder(stream, {mimeType, audioBitsPerSecond: 64000});
      recorder = active;
      const chunks = [];
      let size = 0;
      let failure = "";
      active.ondataavailable = (event) => {
        if (current !== generation || failure || !event.data.size) return;
        size += event.data.size;
        if (size > maxBytes) {
          failure = "The recording exceeds 4 MiB. Make a shorter recording.";
          chunks.length = 0;
          if (active.state === "recording") active.stop();
          releaseMicrophone();
          return;
        }
        chunks.push(event.data);
      };
      active.onerror = () => {
        if (current !== generation) return;
        discard();
        message("Recording failed. Check your microphone and try again.", true);
      };
      active.onstop = () => {
        if (current !== generation) return;
        releaseMicrophone();
        recorder = null;
        const audio = new Blob(chunks, {type: active.mimeType || mimeType});
        if (failure || !audio.size) {
          phase = "idle";
          message(failure || "The recording is empty. Record again.", true);
          controls();
          return;
        }
        upload(audio, current);
      };
      active.start(250);
      started = Date.now();
      phase = "recording";
      message("Recording… Stop when you have finished speaking.");
      find("timer").textContent = `0 / ${maxSeconds} s`;
      timer = setInterval(() => {
        const elapsed = Math.floor((Date.now() - started) / 1000);
        find("timer").textContent = `${Math.min(elapsed, maxSeconds)} / ${maxSeconds} s`;
        if (elapsed >= maxSeconds) stop();
      }, 250);
      controls();
    } catch (error) {
      if (current !== generation) return;
      releaseMicrophone();
      recorder = null;
      phase = "idle";
      const messages = {
        NotAllowedError: "Microphone access was denied. Allow it in your browser's site settings, or continue typing.",
        NotFoundError: "No microphone was found. Connect one or continue typing.",
        NotReadableError: "The microphone is unavailable or in use. Check it and try again.",
      };
      message(messages[error.name] || error.message || "Could not start recording.", true);
      controls();
    }
  }

  function stop() {
    if (phase !== "recording" || !recorder) return;
    phase = "stopping";
    recorder.stop();
    releaseMicrophone();
    controls();
  }

  find("record").addEventListener("click", record);
  find("stop").addEventListener("click", stop);
  find("cancel").addEventListener("click", () => {
    const processing = ["transcribing", "interpreting"].includes(phase);
    discard();
    if (processing) draftMessage("Request cancelled. You can edit the request or search lines manually.");
    message(processing ? "Request cancelled." : "Recording discarded.");
  });
  find("retry").addEventListener("click", () => {
    if (phase === "idle" && retryAudio) upload(retryAudio, ++generation);
  });
  find("paste").addEventListener("click", () => {
    showReview();
    message("Enter a request, then choose Interpret request to prepare search lines.");
    transcript.focus();
  });
  find("interpret").addEventListener("click", () => {
    if (phase === "idle") interpret(++generation);
  });
  function requestChanged() {
    draftReady = false;
    find("notes").replaceChildren();
    draftMessage("Request changed. Interpret it again, or edit the search lines manually.");
    controls();
  }
  transcript.addEventListener("input", requestChanged);
  queries.addEventListener("input", () => {
    draftReady = true;
    find("notes").replaceChildren();
    draftMessage(validLines(queryLines(queries.value))
      ? "Search lines edited. Review them against your request before adding."
      : `Use 1–${config.max_queries} search lines, each at most ${config.max_query_length} characters and ${config.max_query_terms} words.`,
    !validLines(queryLines(queries.value)));
    controls();
  });
  find("use").addEventListener("click", () => {
    const lines = queryLines(queries.value);
    if (phase !== "idle" || input.disabled || !draftReady || !validLines(lines)) return;
    const combined = [input.value.trim(), lines.join("\n")].filter(Boolean).join("\n");
    if (queryLines(combined).length > config.max_queries) {
      message(`Adding these lines would exceed ${config.max_queries} searches. Remove some existing lines first.`, true);
      return;
    }
    if (combined.length > 8192) {
      message("The combined search text is too long. Shorten it before adding.", true);
      return;
    }
    input.value = combined;
    input.dispatchEvent(new Event("input", {bubbles: true}));
    input.dispatchEvent(new Event("change", {bubbles: true}));
    input.dispatchEvent(new CustomEvent("finder:interpreted-added", {detail: {queries: lines}}));
    find("last-transcript").textContent = transcript.value;
    find("last-queries").textContent = lines.join("\n");
    find("last").hidden = false;
    find("last").open = false;
    transcript.value = "";
    queries.value = "";
    draftReady = false;
    find("notes").replaceChildren();
    find("query-review").hidden = true;
    find("review").hidden = true;
    find("workspace").hidden = true;
    find("workspace").open = false;
    controls();
    input.focus();
    message("Added to parts to find. Review the lines, then press Search parts.");
  });
  document.addEventListener("finder:clear-searches", () => {
    discard();
    resetTimings();
    transcript.value = "";
    queries.value = "";
    draftReady = false;
    find("notes").replaceChildren();
    draftMessage("");
    find("query-review").hidden = true;
    find("review").hidden = true;
    find("workspace").hidden = true;
    find("workspace").open = false;
    find("last").hidden = true;
    find("last-transcript").textContent = "";
    find("last-queries").textContent = "";
    message("Speak an English request or paste a sentence to prepare search lines.");
    controls();
  });
  new MutationObserver(controls).observe(input, {attributes: true, attributeFilter: ["disabled"]});
  window.addEventListener("pagehide", discard);
  supported = Boolean(interpreterReady && window.isSecureContext && navigator.mediaDevices?.getUserMedia
    && window.MediaRecorder && MediaRecorder.isTypeSupported);
  if (!supported) {
    message(!interpreterReady ? "Restart InvenTree and refresh this page to enable the updated voice tools. Typed search remains available." : window.isSecureContext
      ? "Voice recording is unavailable in this browser. You can continue typing."
      : "Open Part Finder over HTTPS to use the microphone. You can continue typing.");
  }
  controls();
})();
