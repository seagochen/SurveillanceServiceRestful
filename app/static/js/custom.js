// 监听 htmx 从后端触发的自定义事件
document.body.addEventListener('showsuccessmodal', function(event) {
    
    // 打印日志，确认事件已被接收
    console.log('JavaScript event listener fired! Message:', event.detail.value);
    
    // 1. 获取弹窗元素和用于显示消息的 <p> 标签
    const modal = document.getElementById('success-modal');
    const messageP = document.getElementById('modal-message');

    if (modal && messageP) {
        // 2. 将后端传来的消息设置为弹窗内容
        messageP.textContent = event.detail.value;

        // 3. 显示弹窗
        modal.style.display = 'block';

        // 4. 设置一个2秒的定时器
        setTimeout(() => {
            // 2秒后，隐藏弹窗
            modal.style.display = 'none';
            
            // 并且跳转到主页
            window.location.href = '/';
        }, 2000);
    }
});


// 监听 htmx 从后端触发的自定义事件
document.body.addEventListener('showsuccessmodal', function(event) {
    
    console.log('JavaScript event listener fired! Message:', event.detail.value);
    
    const modal = document.getElementById('success-modal');
    const messageP = document.getElementById('modal-message');

    if (modal && messageP) {
        messageP.textContent = event.detail.value;
        modal.style.display = 'block';

        setTimeout(() => {
            modal.style.display = 'none';
            window.location.href = '/';
        }, 2000);
    }
});

// 【新追加】確認ダイアログを表示し、アクションを制御する関数
function showConfirmationModal(message, url, method) {
    const modal = document.getElementById('confirmation-modal');
    const messageP = document.getElementById('confirmation-message');
    const confirmBtn = document.getElementById('confirm-btn');
    const cancelBtn = document.getElementById('cancel-btn');

    if (!modal || !messageP || !confirmBtn || !cancelBtn) {
        console.error('Confirmation modal elements not found!');
        return;
    }

    // 1. メッセージを設定してダイアログを表示
    messageP.textContent = message;
    modal.style.display = 'flex';

    // 2. キャンセルボタンの動作
    cancelBtn.onclick = function() {
        modal.style.display = 'none';
    };

    // 3. 確認ボタンの動作
    confirmBtn.onclick = function() {
        // ダイアログを非表示
        modal.style.display = 'none';

        // htmx を使ってリクエストをプログラム的に送信
        htmx.ajax(method, url, {
            target: '#main-content', // This target is not strictly necessary if backend only sends HX-Trigger
            swap: 'innerHTML'      // This swap is not strictly necessary if backend only sends HX-Trigger
        }).then(data => {
            // 成功した場合、成功メッセージを表示するイベントをトリガーすることも可能
            // 例えば、バックエンドが成功メッセージを返した場合
            // The backend will now send HX-Trigger, so this block might not be strictly needed for success modals
            // if (data.message) {
            //      htmx.trigger('body', 'showsuccessmodal', { value: data.message });
            // }
            // For error handling or if backend doesn't send HX-Trigger for all cases:
            // if (!data && !event.detail.elt.hasAttribute('hx-trigger')) { // Check if HX-Trigger was not sent by backend
            //     htmx.trigger('body', 'showsuccessmodal', { value: "Operation completed successfully!" });
            // }
        }).catch(error => {
            console.error('HTMX request failed:', error);
            htmx.trigger('body', 'showsuccessmodal', { value: "操作が失敗しました！" }); // Show error message
        });
    };
}

// 切换密码可见性（显示/隐藏）
function togglePasswordVisibility() {
    const input = document.getElementById('password');
    const icon = document.querySelector('.toggle-password');
    if (input && icon) {
        if (input.type === 'password') {
            input.type = 'text';
            icon.textContent = '🙈';
        } else {
            input.type = 'password';
            icon.textContent = '👁️';
        }
    }
}