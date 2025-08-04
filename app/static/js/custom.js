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