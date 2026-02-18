(function () {
  const API = "/api";
  let currentPage = 1;
  let totalPages = 1;
  const perPage = 20;

  const el = {
    searchInput: document.getElementById("search-input"),
    searchBtn: document.getElementById("search-btn"),
    dbSelect: document.getElementById("db-select"),
    saveBtn: document.getElementById("save-btn"),
    message: document.getElementById("message"),
    resultsPanel: document.getElementById("results-panel"),
    resultsList: document.getElementById("results-list"),
    pagination: document.getElementById("pagination"),
    editorSection: document.getElementById("editor-section"),
    postUuid: document.getElementById("post-uuid"),
    postDb: document.getElementById("post-db"),
    postTitle: document.getElementById("post-title"),
    postContentFormat: document.getElementById("post-content-format"),
    formatBadge: document.getElementById("format-badge"),
    postContent: document.getElementById("post-content"),
    postContentSource: document.getElementById("post-content-source"),
    contentEditorWrap: document.getElementById("content-editor-wrap"),
    toggleSourceBtn: document.getElementById("toggle-source-btn"),
    postPath: document.getElementById("post-path"),
    postDate: document.getElementById("post-date"),
    postImage: document.getElementById("post-image"),
    preview: document.getElementById("preview"),
  };

  var isSourceView = false;
  var rawMarkdown = null;

  function getContentFormat() {
    return (el.postContentFormat && el.postContentFormat.value) ? el.postContentFormat.value.toLowerCase() : "html";
  }

  function getEditorContent() {
    return el.postContent ? el.postContent.innerHTML : "";
  }

  function setEditorContent(html) {
    if (el.postContent) el.postContent.innerHTML = html || "";
  }

  function getContent() {
    if (isSourceView && el.postContentSource) return el.postContentSource.value;
    return getEditorContent();
  }

  function setContent(html) {
    setEditorContent(html);
    if (el.postContentSource) el.postContentSource.value = html || "";
  }

  function toggleSourceView() {
    var format = getContentFormat();
    isSourceView = !isSourceView;
    if (isSourceView) {
      if (el.postContentSource) {
        if (format === "md") {
          if (rawMarkdown !== null) {
            el.postContentSource.value = rawMarkdown;
          } else {
            var md = htmlToMarkdown(getEditorContent());
            el.postContentSource.value = md;
            rawMarkdown = md;
          }
        } else {
          el.postContentSource.value = getEditorContent();
        }
        el.postContentSource.classList.add("show");
        updatePreview(el.postContentSource.value, format);
      }
      if (el.contentEditorWrap) el.contentEditorWrap.classList.add("hide");
      if (el.toggleSourceBtn) el.toggleSourceBtn.textContent = "View editor";
    } else {
      var sourceVal = el.postContentSource ? el.postContentSource.value : "";
      if (format === "md") {
        rawMarkdown = sourceVal;
        setEditorContent(renderMarkdown(sourceVal));
      } else {
        rawMarkdown = null;
        setEditorContent(sourceVal);
      }
      if (el.contentEditorWrap) el.contentEditorWrap.classList.remove("hide");
      if (el.postContentSource) el.postContentSource.classList.remove("show");
      if (el.toggleSourceBtn) el.toggleSourceBtn.textContent = "View source";
      updatePreview(getEditorContent(), "html");
    }
  }

  function renderMarkdown(md) {
    if (typeof marked === "undefined" || !md) return md || "";
    return (marked.parse || marked)(md);
  }

  function htmlToMarkdown(html) {
    if (!html) return "";
    if (typeof TurndownService === "undefined") return html;
    try {
      var td = new TurndownService();
      return td.turndown(html);
    } catch (e) {
      return html;
    }
  }

  function showMessage(text, type) {
    if (el.message) {
      el.message.textContent = text || "";
      el.message.className = "message" + (type ? " " + type : "");
    }
  }

  function showError(err) {
    const text = err?.message || err?.detail || String(err);
    showMessage(text, "error");
  }

  function showSuccess(text) {
    showMessage(text, "success");
  }

  async function fetchJson(url, options = {}) {
    const res = await fetch(url, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || res.statusText);
    }
    return res.json();
  }

  async function loadDatabases() {
    const list = await fetchJson(API + "/databases");
    el.dbSelect.innerHTML = '<option value="all">All</option>';
    list.forEach(({ index, name }) => {
      const opt = document.createElement("option");
      opt.value = index;
      opt.textContent = name;
      el.dbSelect.appendChild(opt);
    });
  }

  function renderResultItem(post) {
    const div = document.createElement("button");
    div.type = "button";
    div.className = "result-item";
    div.innerHTML =
      '<span class="title">' +
      escapeHtml(post.title || "(no title)") +
      "</span>" +
      '<span class="meta">db' +
      post.db +
      " · " +
      (post.date || "") +
      "</span>";
    div.addEventListener("click", () => loadPost(post.uuid, post.db));
    return div;
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  async function search() {
    const title = (el.searchInput && el.searchInput.value) ? el.searchInput.value.trim() : "";
    if (!title) {
      currentPage = 1;
      listPosts();
      return;
    }
    showMessage("Searching…");
    try {
      const items = await fetchJson(API + "/posts/search?title=" + encodeURIComponent(title));
      el.resultsList.innerHTML = "";
      if (items.length === 0) {
        el.resultsList.innerHTML = "<p>No results.</p>";
      } else {
        items.forEach((post) => el.resultsList.appendChild(renderResultItem(post)));
      }
      el.pagination.innerHTML = "";
      showMessage("");
    } catch (e) {
      showError(e);
    }
  }

  async function listPosts() {
    const db = el.dbSelect.value;
    showMessage("Loading…");
    try {
      const data = await fetchJson(
        API + "/posts?db=" + encodeURIComponent(db) + "&page=" + currentPage + "&per_page=" + perPage
      );
      el.resultsList.innerHTML = "";
      if (data.items.length === 0) {
        el.resultsList.innerHTML = "<p>No posts.</p>";
      } else {
        data.items.forEach((post) => el.resultsList.appendChild(renderResultItem(post)));
      }
      totalPages = Math.max(1, Math.ceil(data.total / perPage));
      renderPagination(data.total, data.page);
      showMessage("");
    } catch (e) {
      showError(e);
    }
  }

  function renderPagination(total, page) {
    el.pagination.innerHTML = "";
    const prev = document.createElement("button");
    prev.type = "button";
    prev.textContent = "Previous";
    prev.disabled = page <= 1;
    prev.addEventListener("click", () => {
      currentPage = page - 1;
      listPosts();
    });
    el.pagination.appendChild(prev);
    const info = document.createElement("span");
    info.textContent = "Page " + page + " of " + totalPages + " (" + total + " items)";
    el.pagination.appendChild(info);
    const next = document.createElement("button");
    next.type = "button";
    next.textContent = "Next";
    next.disabled = page >= totalPages;
    next.addEventListener("click", () => {
      currentPage = page + 1;
      listPosts();
    });
    el.pagination.appendChild(next);
  }

  function setVal(element, value) {
    if (element && "value" in element) element.value = value;
  }

  function getTitleFromPost(post) {
    return post.title ?? post["title"] ?? "";
  }

  async function loadPost(uuid, db) {
    showMessage("Loading…");
    try {
      const post = await fetchJson(API + "/posts/by-id?uuid=" + encodeURIComponent(uuid) + "&db=" + db);
      setVal(el.postUuid, String(post.uuid != null ? post.uuid : ""));
      setVal(el.postDb, String(post.db != null ? post.db : ""));
      var titleVal = String(getTitleFromPost(post));
      setVal(el.postTitle, titleVal);
      var titleInput = document.getElementById("post-title");
      if (titleInput && titleInput.value !== titleVal) titleInput.value = titleVal;
      setVal(el.postPath, String(post.path != null ? post.path : ""));
      setVal(el.postDate, String(post.date != null ? post.date : ""));
      setVal(el.postImage, String(post.image != null ? post.image : ""));
      const format = (post.content_format != null ? post.content_format : "html").toString().toLowerCase();
      setVal(el.postContentFormat, format);
      if (el.formatBadge) el.formatBadge.textContent = "Format: " + format.toUpperCase();
      var contentHtml = post.content != null ? post.content : "";
      if (format === "md") {
        rawMarkdown = post.content != null ? post.content : "";
        contentHtml = renderMarkdown(rawMarkdown);
      } else {
        rawMarkdown = null;
      }
      setEditorContent(contentHtml);
      if (el.postContentSource) el.postContentSource.value = format === "md" ? rawMarkdown : contentHtml;
      isSourceView = false;
      if (el.contentEditorWrap) el.contentEditorWrap.classList.remove("hide");
      if (el.postContentSource) el.postContentSource.classList.remove("show");
      if (el.toggleSourceBtn) el.toggleSourceBtn.textContent = "View source";
      updatePreview(post.content != null ? post.content : "", format);
      if (el.editorSection) el.editorSection.hidden = false;
      if (el.saveBtn) el.saveBtn.disabled = false;
      showMessage("");
    } catch (e) {
      showError(e);
    }
  }

  function updatePreview(content, format) {
    if (content == null) content = getEditorContent();
    if (format == null) format = el.postContentFormat ? el.postContentFormat.value : "html";
    var html;
    if (format === "md") {
      html = renderMarkdown(content);
    } else {
      html = content;
    }
    if (el.preview) el.preview.innerHTML = html || "<em>Empty</em>";
  }

  var savedRange = null;

  function saveSelection() {
    var sel = window.getSelection();
    if (!sel.rangeCount || !el.postContent || !el.postContent.contains(sel.anchorNode)) return;
    savedRange = sel.getRangeAt(0).cloneRange();
  }

  function restoreSelection() {
    if (!savedRange || !el.postContent) return false;
    var sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(savedRange);
    return true;
  }

  if (el.postContent) {
    el.postContent.addEventListener("input", function () {
      rawMarkdown = null;
      updatePreview(getEditorContent(), "html");
    });
    el.postContent.addEventListener("blur", () => updatePreview(getEditorContent(), "html"));
    el.postContent.addEventListener("mouseup", saveSelection);
    el.postContent.addEventListener("keyup", saveSelection);
  }
  if (el.postContentSource) {
    el.postContentSource.addEventListener("input", function () {
      if (isSourceView) updatePreview(this.value, getContentFormat());
    });
  }
  if (el.toggleSourceBtn) {
    el.toggleSourceBtn.addEventListener("click", toggleSourceView);
  }

  document.querySelectorAll(".rich-editor-toolbar button").forEach(function (btn) {
    var cmd = btn.getAttribute("data-cmd");
    if (cmd === "createLink") {
      btn.addEventListener("mousedown", function () { saveSelection(); });
    }
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      var arg = btn.getAttribute("data-arg") || null;
      if (cmd === "createLink") {
        var url = prompt("URL do link:", "https://");
        if (!url || !(url = url.trim())) return;
        el.postContent.focus();
        restoreSelection();
        document.execCommand(cmd, false, url);
      } else {
        el.postContent.focus();
        document.execCommand(cmd, false, arg);
      }
      updatePreview(getEditorContent(), "html");
    });
  });

  document.getElementById("save-btn").addEventListener("click", async () => {
    var uuidEl = el.postUuid || document.getElementById("post-uuid");
    var dbEl = el.postDb || document.getElementById("post-db");
    var titleEl = el.postTitle || document.getElementById("post-title");
    var pathEl = el.postPath || document.getElementById("post-path");
    var dateEl = el.postDate || document.getElementById("post-date");
    var imageEl = el.postImage || document.getElementById("post-image");
    var uuid = uuidEl ? uuidEl.value : "";
    var db = dbEl ? parseInt(dbEl.value, 10) : 0;
    if (!uuid || !db) return;
    var fmt = getContentFormat();
    var body = {
      db: db,
      title: titleEl ? titleEl.value : "",
      content: getContent(),
      content_format: (fmt === "md" && isSourceView) ? "md" : "html",
      path: pathEl ? pathEl.value : "",
      date: dateEl ? dateEl.value : "",
      image: imageEl ? imageEl.value : "",
    };
    showMessage("Saving…");
    try {
      var res = await fetch(API + "/posts/" + encodeURIComponent(uuid), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        var data = await res.json().catch(function () { return {}; });
        throw new Error(data.detail || res.statusText);
      }
      showSuccess("Post updated.");
    } catch (e) {
      showError(e);
    }
  });

  el.searchBtn.addEventListener("click", search);
  el.searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") search();
  });

  loadDatabases()
    .then(function () {
      currentPage = 1;
      listPosts();
    })
    .catch(showError);
})();
