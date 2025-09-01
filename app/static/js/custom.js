// 弹出消息 toggle window
document.body.addEventListener('showsuccessmodal', function(event) {
    const val = event.detail?.value;
    const message = (typeof val === 'string') ? val : (val?.message || '操作が完了しました。');
    const delay = (typeof val === 'object' && typeof val.delay === 'number') ? val.delay : 2000;

    const modal = document.getElementById('success-modal');
    const messageP = document.getElementById('modal-message');
    if (!modal || !messageP) return;

    messageP.textContent = message;
    modal.style.display = 'block';
    setTimeout(() => {
        modal.style.display = 'none';
    }, delay);
});


// 确认对话框：用于“初期設定/読込/同期/再起動”等按钮
function showConfirmationModal(message, url, method) {
    const modal = document.getElementById('confirmation-modal');
    const messageP = document.getElementById('confirmation-message');
    const confirmBtn = document.getElementById('confirm-btn');
    const cancelBtn = document.getElementById('cancel-btn');

    if (!modal || !messageP || !confirmBtn || !cancelBtn) {
        console.error('Confirmation modal elements not found!');
        return;
    }

    // 1) 显示对话框
    messageP.textContent = message;
    modal.style.display = 'flex';

    // 2) 取消
    cancelBtn.onclick = function() {
        modal.style.display = 'none';
    };

    // 3) 确认：发起 htmx 请求（后端会通过 HX-Trigger 弹窗并跳转）
    confirmBtn.onclick = function() {
        modal.style.display = 'none';
        htmx.ajax(method, url, {
            // target: '#main-content', // 后端主要靠 HX-Trigger，所以 target/swap 不是必须
            // swap: 'innerHTML'
        }).catch(error => {
            console.error('HTMX request failed:', error);
            htmx.trigger('body', 'showsuccessmodal', { value: "操作が失敗しました！" });
        });
    };
}


// 切换密码可见性
function togglePasswordVisibility() {
    const input = document.getElementById('password');
    const icon = document.querySelector('.toggle-password');
    if (!input || !icon) return;
    if (input.type === 'password') {
        input.type = 'text';
        icon.textContent = '🙈';
    } else {
        input.type = 'password';
        icon.textContent = '👁️';
    }
}
