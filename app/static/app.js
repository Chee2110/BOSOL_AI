/**
 * ==============================================================================
 * BOSOL AI - CHATGPT INSPIRED CLEAN & BRIGHT FRONTEND ENGINE
 * ==============================================================================
 */

let currentJob = null;
let currentPdfDoc = null;
let currentPageNumber = 1;
let currentScale = 1.0;
let bomItems = [];
let activeItemId = null;
let isViewerVisible = true;

document.addEventListener("DOMContentLoaded", () => {
    initApp();
    setupEventListeners();
});

async function initApp() {
    await fetchSystemStatus();
    await fetchSampleList();
    await fetchRecentList();
}

function setupEventListeners() {
    // 1. Sidebar Toggle
    document.getElementById("btn-toggle-sidebar").addEventListener("click", () => {
        document.getElementById("sidebar").classList.toggle("collapsed");
    });

    // 2. Nút "Bản Vẽ Mới"
    document.getElementById("btn-new-drawing").addEventListener("click", () => {
        showWelcomeScreen();
    });

    // 3. Kéo thả file ở Welcome screen
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input-welcome");

    dropZone.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => {
        if (e.target.files[0]) handleUploadFile(e.target.files[0]);
    });

    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });
    dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (e.dataTransfer.files[0]) handleUploadFile(e.dataTransfer.files[0]);
    });

    // 4. Click các thẻ gợi ý (4 Prompt Cards)
    document.querySelectorAll(".prompt-card").forEach(card => {
        card.addEventListener("click", () => {
            const samplePath = card.getAttribute("data-sample");
            if (samplePath) loadSample(samplePath);
        });
    });

    // 5. Nút Duyệt Nhanh 1-Chạm
    document.getElementById("btn-bulk-approve").addEventListener("click", handleBulkApprove);

    // 6. Nút Xuất ERP (Hard Gate 2 lớp)
    document.getElementById("btn-export-erp").addEventListener("click", handleExportERP);

    // 7. Ẩn/Hiện Khung Bản Vẽ
    document.getElementById("btn-toggle-viewer").addEventListener("click", () => {
        isViewerVisible = !isViewerVisible;
        const viewer = document.getElementById("pane-viewer");
        const btn = document.getElementById("btn-toggle-viewer");
        if (isViewerVisible) {
            viewer.style.display = "flex";
            btn.innerHTML = "<span>📐 Ẩn Bản Vẽ</span>";
        } else {
            viewer.style.display = "none";
            btn.innerHTML = "<span>📐 Hiện Bản Vẽ</span>";
        }
    });

    // 8. Điều khiển Zoom & Trang bản vẽ
    document.getElementById("btn-zoom-in").addEventListener("click", () => adjustZoom(0.2));
    document.getElementById("btn-zoom-out").addEventListener("click", () => adjustZoom(-0.2));
    document.getElementById("btn-zoom-fit").addEventListener("click", fitPageWidth);
    document.getElementById("btn-prev-page").addEventListener("click", () => changePageNum(-1));
    document.getElementById("btn-next-page").addEventListener("click", () => changePageNum(1));

    // 9. Chat Copilot ChatGPT style
    const chatInput = document.getElementById("copilot-input");
    const sendBtn = document.getElementById("btn-send-chat");

    sendBtn.addEventListener("click", handleSendChat);
    chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") handleSendChat();
    });

    // 10. Modal Close
    document.getElementById("btn-close-modal").addEventListener("click", closeModal);
    document.getElementById("image-modal").addEventListener("click", (e) => {
        if (e.target.id === "image-modal") closeModal();
    });
}

/* ==============================================================================
   API FETCHING & SIDEBAR LISTS
   ============================================================================== */

async function fetchSystemStatus() {
    try {
        const res = await fetch("/api/system/status");
        if (!res.ok) return;
        const data = await res.json();

        document.getElementById("sys-db").textContent = data.db_mode;
        document.getElementById("sys-model").textContent = data.gemini_model;

        const spend = data.today_spent_usd || 0;
        const maxBudget = data.max_daily_budget_usd || 2.0;
        const pct = Math.min(100, (spend / maxBudget) * 100);
        document.getElementById("mini-budget-val").textContent = `$${spend.toFixed(4)} / $${maxBudget.toFixed(2)}`;
        document.getElementById("mini-budget-fill").style.width = `${Math.max(2, pct)}%`;
    } catch (err) {
        console.error("Lỗi lấy trạng thái hệ thống:", err);
    }
}

async function fetchSampleList() {
    try {
        const res = await fetch("/api/sample-files");
        if (!res.ok) return;
        const data = await res.json();
        const container = document.getElementById("sample-list");
        container.innerHTML = "";

        const icons = {
            "PDF_BANVE": "📐",
            "PDF_SCAN_BAN_VE": "📑",
            "PDF_SCAN_TEXT": "📄",
            "PDF_TEXT": "📋"
        };

        for (const [cat, files] of Object.entries(data.categories)) {
            files.forEach(f => {
                const item = document.createElement("div");
                item.className = "nav-item";
                item.title = `${f.filename} (${f.size_kb} KB)`;
                item.innerHTML = `
                    <span class="item-icon">${icons[cat] || "📄"}</span>
                    <span class="item-text">${f.filename}</span>
                `;
                item.addEventListener("click", () => loadSample(f.relative_path));
                container.appendChild(item);
            });
        }
    } catch (err) {
        console.error("Lỗi danh mục mẫu:", err);
    }
}

async function fetchRecentList() {
    try {
        const res = await fetch("/api/jobs");
        if (!res.ok) return;
        const data = await res.json();
        const container = document.getElementById("recent-list");
        container.innerHTML = "";

        if (!data.jobs || data.jobs.length === 0) {
            container.innerHTML = '<span style="font-size: 11px; color: var(--text-muted); padding: 4px 8px;">Chưa có bản vẽ nào.</span>';
            return;
        }

        data.jobs.slice(0, 10).forEach(j => {
            const item = document.createElement("div");
            item.className = "nav-item";
            if (currentJob && currentJob.id === j.id) item.classList.add("active");
            item.innerHTML = `
                <span class="status-indicator ${j.review_status === 'approved' ? 'online' : ''}" style="background-color: ${j.review_status === 'approved' ? '#10a37f' : '#f59e0b'};"></span>
                <span class="item-text">${j.filename}</span>
            `;
            item.addEventListener("click", () => loadJob(j.id));
            container.appendChild(item);
        });
    } catch (err) {
        console.error("Lỗi danh sách gần đây:", err);
    }
}

/* ==============================================================================
   LOADING & SWITCHING WORKSPACE
   ============================================================================== */

function showWelcomeScreen() {
    currentJob = null;
    document.getElementById("welcome-screen").style.display = "flex";
    document.getElementById("workspace-dual").style.display = "none";
    document.getElementById("top-filename").textContent = "Trang Chủ";
    document.getElementById("top-category-badge").style.display = "none";
    document.getElementById("btn-toggle-viewer").style.display = "none";
    document.getElementById("btn-bulk-approve").style.display = "none";
    document.getElementById("btn-export-erp").style.display = "none";
}

async function loadSample(relativePath) {
    showToast(`Đang bóc tách ${relativePath}...`, "info");
    try {
        const res = await fetch("/api/load-sample", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ relative_path: relativePath })
        });
        const data = await res.json();
        if (res.ok) {
            showToast(data.message, "success");
            await loadJob(data.job_id);
            fetchRecentList();
            fetchSystemStatus();
        } else {
            showToast(data.detail || "Không thể nạp bản vẽ mẫu", "error");
        }
    } catch (err) {
        showToast("Lỗi mạng khi nạp bản vẽ", "error");
    }
}

async function handleUploadFile(file) {
    const formData = new FormData();
    formData.append("file", file);

    showToast(`Đang nạp và trích xuất ${file.name}...`, "info");
    try {
        const res = await fetch("/api/upload", {
            method: "POST",
            body: formData
        });
        const data = await res.json();
        if (res.ok) {
            showToast("Bóc tách bản vẽ thành công!", "success");
            await loadJob(data.job_id);
            fetchRecentList();
            fetchSystemStatus();
        } else {
            showToast(data.detail || "Lỗi nạp tệp", "error");
        }
    } catch (err) {
        showToast("Lỗi kết nối", "error");
    }
}

async function loadJob(jobId) {
    try {
        const res = await fetch(`/api/jobs/${jobId}`);
        if (!res.ok) throw new Error("Không thể tải Job");
        const data = await res.json();

        currentJob = data.job;
        bomItems = data.bom_items;

        // Chuyển sang màn hình Workspace
        document.getElementById("welcome-screen").style.display = "none";
        document.getElementById("workspace-dual").style.display = "flex";

        // Thanh điều hướng trên cùng
        document.getElementById("top-filename").textContent = data.document.filename;
        document.getElementById("lead-filename").textContent = data.document.filename;
        const catBadge = document.getElementById("top-category-badge");
        catBadge.textContent = data.document.detected_category;
        catBadge.style.display = "inline-block";

        document.getElementById("btn-toggle-viewer").style.display = "inline-flex";
        document.getElementById("btn-bulk-approve").style.display = "inline-flex";
        document.getElementById("btn-export-erp").style.display = "inline-flex";

        // Render Khung tên (Title Block)
        renderTitleBlock(bomItems);

        // Render Bảng số liệu BOM
        renderBOMItems(bomItems);

        // Cập nhật trạng thái Hard Gate ERP
        updateHardGateState();

        // Tải PDF vào khung xem bên phải
        loadPDFViewer(data.document.pdf_url);

        // Đánh dấu active trong sidebar
        document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("active"));

    } catch (err) {
        console.error("Lỗi nạp Job:", err);
        showToast("Không thể nạp dữ liệu bản vẽ", "error");
    }
}

/* ==============================================================================
   BOM & TITLE BLOCK RENDERING
   ============================================================================== */

function renderTitleBlock(items) {
    let name = "—", mat = "—", scale = "—";
    items.forEach(it => {
        if (it.column_name.includes("title_block_name")) name = it.suggested_value || "—";
        if (it.column_name.includes("title_block_material")) mat = it.suggested_value || "—";
        if (it.column_name.includes("title_block_scale")) scale = it.suggested_value || "—";
    });

    document.getElementById("tb-name").textContent = name;
    document.getElementById("tb-material").textContent = mat;
    document.getElementById("tb-scale").textContent = scale;
}

function renderBOMItems(items) {
    const tbody = document.getElementById("bom-items-tbody");
    tbody.innerHTML = "";

    if (!items || items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 30px;">Không có mục kích thước nào được phát hiện.</td></tr>';
        return;
    }

    items.forEach((it, idx) => {
        const tr = document.createElement("tr");
        tr.id = `item-row-${it.id}`;
        tr.className = it.approval_status === "accepted" ? "row-accepted" : 
                       it.approval_status === "rejected" ? "row-rejected" : "";

        // Tên thông số
        const paramName = formatParam(it.column_name);

        // Bằng chứng WebP Thumbnail
        let proofHtml = '<span style="color: var(--text-muted); font-size: 11px;">0 VNĐ Text</span>';
        if (it.evidence_url) {
            proofHtml = `<img class="crop-thumb" src="${it.evidence_url}" alt="Crop" 
                onclick="event.stopPropagation(); openCropModal('${it.evidence_url}', '${escapeHtml(it.suggested_value)}', '${escapeHtml(paramName)}')" 
                title="Bấm để phóng to ảnh cận cảnh">`;
        }

        const verifiedVal = it.verified_value || it.suggested_value || "";

        tr.innerHTML = `
            <td style="font-family: var(--font-mono); color: var(--text-muted);">${idx + 1}</td>
            <td><strong>${paramName}</strong></td>
            <td>
                <span style="font-family: var(--font-mono); font-weight: 600; color: #0284c7;">${escapeHtml(it.suggested_value || "—")}</span>
                <span style="font-size: 10px; color: var(--text-muted); margin-left: 4px;">(${Math.round(it.confidence * 100)}%)</span>
            </td>
            <td>${proofHtml}</td>
            <td>
                <input type="text" class="edit-val-input" value="${escapeHtml(verifiedVal)}" data-id="${it.id}">
            </td>
            <td style="text-align: center;">
                <button class="btn-row-act check ${it.approval_status === 'accepted' ? 'active' : ''}" 
                    onclick="event.stopPropagation(); setItemApproval('${it.id}', 'accepted')" title="Chấp nhận">✓</button>
                <button class="btn-row-act cross ${it.approval_status === 'rejected' ? 'active' : ''}" 
                    onclick="event.stopPropagation(); setItemApproval('${it.id}', 'rejected')" title="Từ chối">✕</button>
            </td>
        `;

        // Click dòng -> Định vị và highlight trên bản vẽ bên phải
        tr.addEventListener("click", () => highlightBOMItem(it.id));

        // Input change
        const inp = tr.querySelector(".edit-val-input");
        inp.addEventListener("change", (e) => updateBOMValue(it.id, e.target.value));
        inp.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                setItemApproval(it.id, "accepted");
                inp.blur();
            }
        });

        tbody.appendChild(tr);
    });
}

function formatParam(colName) {
    if (!colName) return "Thông số";
    const dict = {
        "title_block_code": "Mã Bản Vẽ",
        "title_block_name": "Tên Bản Vẽ",
        "title_block_material": "Vật Liệu",
        "title_block_scale": "Tỷ Lệ",
        "dim_diameter": "Đường Kính (Ø)",
        "dim_radius": "Bán Kính (R)",
        "dim_tolerance": "Dung Sai (±)",
        "dim_thread": "Ren Ốc (M)",
        "dim_linear": "Kích Thước Dài (mm)"
    };
    return dict[colName] || colName;
}

function highlightBOMItem(itemId) {
    activeItemId = itemId;

    // Highlight row
    document.querySelectorAll(".chatgpt-table tbody tr").forEach(r => r.classList.remove("active"));
    const activeRow = document.getElementById(`item-row-${itemId}`);
    if (activeRow) activeRow.classList.add("active");

    // Highlight BBox on drawing
    document.querySelectorAll(".bbox-tag").forEach(b => b.classList.remove("focused"));
    const targetBox = document.getElementById(`bbox-tag-${itemId}`);
    if (targetBox) {
        targetBox.classList.add("focused");
        targetBox.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
    }
}

/* ==============================================================================
   REVIEW ACTIONS & HARD GATE ERP
   ============================================================================== */

async function setItemApproval(itemId, status) {
    const item = bomItems.find(it => it.id === itemId);
    if (!item) return;

    const row = document.getElementById(`item-row-${itemId}`);
    const input = row.querySelector(".edit-val-input");
    const val = input.value.trim() || item.suggested_value || "0";

    try {
        const res = await fetch(`/api/bom/${itemId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                approval_status: status,
                verified_value: val
            })
        });
        const data = await res.json();
        if (res.ok) {
            item.approval_status = data.approval_status;
            item.verified_value = data.verified_value;
            currentJob.review_status = data.job_review_status;

            row.className = status === "accepted" ? "row-accepted" : "row-rejected";
            row.querySelector(".btn-row-act.check").classList.toggle("active", status === "accepted");
            row.querySelector(".btn-row-act.cross").classList.toggle("active", status === "rejected");

            updateHardGateState();
            showToast(`Đã ${status === 'accepted' ? 'duyệt' : 'từ chối'} số liệu!`, "success");
        }
    } catch (err) {
        showToast("Lỗi khi cập nhật trạng thái duyệt", "error");
    }
}

async function updateBOMValue(itemId, newVal) {
    const item = bomItems.find(it => it.id === itemId);
    if (!item) return;

    try {
        await fetch(`/api/bom/${itemId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                approval_status: "modified",
                verified_value: newVal
            })
        });
        item.verified_value = newVal;
        item.approval_status = "modified";
        updateHardGateState();
        showToast("Đã lưu số đo chỉnh sửa!", "info");
    } catch (err) {
        showToast("Lỗi khi lưu số liệu", "error");
    }
}

async function handleBulkApprove() {
    if (!currentJob) return;
    try {
        const res = await fetch(`/api/jobs/${currentJob.id}/bulk-approve`, { method: "POST" });
        const data = await res.json();
        if (res.ok) {
            showToast(data.message, "success");
            await loadJob(currentJob.id);
        }
    } catch (err) {
        showToast("Lỗi khi duyệt toàn bộ", "error");
    }
}

function updateHardGateState() {
    const total = bomItems.length;
    const approved = bomItems.filter(it => it.approval_status === "accepted").length;

    document.getElementById("tb-progress").textContent = `${approved}/${total} mục`;

    const btnExport = document.getElementById("btn-export-erp");
    const notice = document.getElementById("hardgate-notice");
    const noticeIcon = document.getElementById("notice-icon");
    const noticeTitle = document.getElementById("notice-title");
    const noticeDesc = document.getElementById("notice-desc");

    if (total > 0 && approved === total) {
        // MỞ KHÓA HOÀN TOÀN
        btnExport.className = "btn btn-erp-gate unlocked";
        btnExport.disabled = false;
        btnExport.innerHTML = "<span>🚀 Xuất Dữ Liệu ERP</span>";

        notice.className = "hardgate-notice unlocked";
        noticeIcon.textContent = "🔓";
        noticeTitle.textContent = "Đã Hoàn Thành Đối Soát Kỹ Sư (100% Sẵn Sàng)";
        noticeDesc.textContent = "Toàn bộ thông số kích thước đã được xác thực chính xác. Bạn có thể xuất file xuống xưởng.";
    } else {
        // KHÓA CỨNG
        btnExport.className = "btn btn-erp-gate";
        btnExport.disabled = true;
        btnExport.innerHTML = `<span>🔒 Khóa Xuất ERP (${total - approved})</span>`;

        notice.className = "hardgate-notice";
        noticeIcon.textContent = "🔒";
        noticeTitle.textContent = "Khóa An Toàn 2 Lớp (Hard Gate ERP)";
        noticeDesc.textContent = `Còn ${total - approved}/${total} mục chưa được duyệt. Chặn đứng lỗi gửi sai số đo xuống máy cắt CNC.`;
    }
}

async function handleExportERP() {
    if (!currentJob) return;
    try {
        const res = await fetch(`/api/jobs/${currentJob.id}/export-erp`, { method: "POST" });
        if (res.status === 403) {
            const err = await res.json();
            showToast(err.detail, "error");
            return;
        }

        if (res.ok) {
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `BOM_${currentJob.id.slice(0, 8)}_APPROVED.csv`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            showToast("Tải xuống tệp dữ liệu sản xuất ERP thành công!", "success");
        }
    } catch (err) {
        showToast("Lỗi khi xuất tệp dữ liệu", "error");
    }
}

/* ==============================================================================
   CHAT COPILOT CHATGPT STYLE
   ============================================================================== */

async function handleSendChat() {
    const input = document.getElementById("copilot-input");
    const msg = input.value.trim();
    if (!msg) return;

    input.value = "";

    // 1. Thêm tin nhắn của User
    appendChatMessage("user", msg);

    // 2. Thêm bubble loading của Assistant
    const loadingId = appendChatMessage("assistant", "Đang suy nghĩ...");

    try {
        const res = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                job_id: currentJob ? currentJob.id : null,
                message: msg
            })
        });
        const data = await res.json();
        updateChatMessage(loadingId, data.reply || "Xin lỗi, tôi không thể xử lý câu hỏi này.");
    } catch (err) {
        updateChatMessage(loadingId, "Lỗi kết nối khi đàm thoại với trợ lý AI.");
    }
}

function appendChatMessage(role, content) {
    const stream = document.getElementById("conversation-stream");
    const id = `msg-${Date.now()}`;
    const div = document.createElement("div");
    div.className = `chat-message ${role}`;
    div.id = id;

    if (role === "user") {
        div.innerHTML = `
            <div class="avatar">👤</div>
            <div class="message-bubble">${escapeHtml(content)}</div>
        `;
    } else {
        div.innerHTML = `
            <div class="avatar">🤖</div>
            <div class="message-content">
                <div class="assistant-lead" style="white-space: pre-wrap;">${escapeHtml(content)}</div>
            </div>
        `;
    }

    stream.appendChild(div);
    div.scrollIntoView({ behavior: "smooth", block: "end" });
    return id;
}

function updateChatMessage(id, newContent) {
    const msgEl = document.getElementById(id);
    if (!msgEl) return;
    const lead = msgEl.querySelector(".assistant-lead");
    if (lead) {
        lead.innerHTML = newContent.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br/>');
    }
}

/* ==============================================================================
   PDF.JS CAD DRAWING VIEWER LIGHT
   ============================================================================== */

async function loadPDFViewer(pdfUrl) {
    if (!pdfUrl) return;
    try {
        const task = pdfjsLib.getDocument(pdfUrl);
        currentPdfDoc = await task.promise;
        currentPageNumber = 1;
        renderPDFPage(currentPageNumber);
    } catch (err) {
        console.error("Lỗi nạp PDF.js:", err);
    }
}

async function renderPDFPage(pageNum) {
    if (!currentPdfDoc) return;

    const page = await currentPdfDoc.getPage(pageNum);
    const canvas = document.getElementById("pdf-render-canvas");
    const ctx = canvas.getContext("2d");

    const scrollArea = document.getElementById("canvas-scroll-area");
    const targetW = scrollArea.clientWidth - 50;
    const baseVp = page.getViewport({ scale: 1.0 });

    if (currentScale === 1.0) {
        currentScale = targetW / baseVp.width;
    }

    const viewport = page.getViewport({ scale: currentScale });
    canvas.width = viewport.width;
    canvas.height = viewport.height;

    await page.render({ canvasContext: ctx, viewport: viewport }).promise;

    document.getElementById("page-num-display").textContent = `${pageNum} / ${currentPdfDoc.numPages}`;
    document.getElementById("zoom-percent").textContent = `${Math.round(currentScale * 100)}%`;

    renderBBoxes(viewport, pageNum);
}

function renderBBoxes(viewport, pageNum) {
    const layer = document.getElementById("bbox-layer");
    layer.innerHTML = "";

    const filtered = bomItems.filter(it => it.page_number === pageNum && it.bbox_pdf && it.bbox_pdf.length === 4);

    filtered.forEach(it => {
        const [x0, y0, x1, y1] = it.bbox_pdf;
        if (x1 <= x0 || y1 <= y0) return;

        const rect = viewport.convertToViewportRectangle([x0, y0, x1, y1]);
        const left = Math.min(rect[0], rect[2]);
        const top = Math.min(rect[1], rect[3]);
        const width = Math.abs(rect[2] - rect[0]);
        const height = Math.abs(rect[3] - rect[1]);

        const box = document.createElement("div");
        box.id = `bbox-tag-${it.id}`;
        box.className = "bbox-tag";
        box.style.left = `${left}px`;
        box.style.top = `${top}px`;
        box.style.width = `${Math.max(width, 14)}px`;
        box.style.height = `${Math.max(height, 14)}px`;
        box.title = `${formatParam(it.column_name)}: ${it.suggested_value}`;

        if (activeItemId === it.id) box.classList.add("focused");

        box.addEventListener("click", () => {
            highlightBOMItem(it.id);
            const row = document.getElementById(`item-row-${it.id}`);
            if (row) row.scrollIntoView({ behavior: "smooth", block: "center" });
        });

        layer.appendChild(box);
    });
}

function adjustZoom(delta) {
    currentScale = Math.max(0.4, Math.min(3.0, currentScale + delta));
    renderPDFPage(currentPageNumber);
}

function fitPageWidth() {
    currentScale = 1.0;
    renderPDFPage(currentPageNumber);
}

function changePageNum(delta) {
    if (!currentPdfDoc) return;
    const target = currentPageNumber + delta;
    if (target >= 1 && target <= currentPdfDoc.numPages) {
        currentPageNumber = target;
        renderPDFPage(currentPageNumber);
    }
}

/* ==============================================================================
   MODAL & TOAST NOTIFICATIONS
   ============================================================================== */

function openCropModal(url, text, label) {
    document.getElementById("modal-crop-image").src = url;
    document.getElementById("modal-sub-info").textContent = `${label} • Giá trị bóc tách: "${text}"`;
    document.getElementById("image-modal").classList.add("active");
}

function closeModal() {
    document.getElementById("image-modal").classList.remove("active");
}

function showToast(msg, type = "info") {
    const stack = document.getElementById("toast-stack");
    const toast = document.createElement("div");
    toast.className = `toast-item ${type}`;

    const icons = { info: "ℹ️", success: "✅", error: "❌" };
    toast.innerHTML = `<span>${icons[type] || "ℹ️"}</span><span>${escapeHtml(msg)}</span>`;

    stack.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 250);
    }, 3200);
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
