// AI投研日报摘要 - 动态加载
// 从 /api/digest 获取实时摘要数据并渲染

function renderAIDigest() {
    var container = document.getElementById('ai-digest-list');
    if (!container) return;

    fetch('/api/digest', {
        cache: 'no-store'
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (!data || !data.items) return;
        container.innerHTML = '';
        data.items.forEach(function(item) {
            var div = document.createElement('div');
            div.className = 'digest-item';
            div.innerHTML = '<span class="digest-tag ' + item.tag + '">' + item.label + '</span><span class="digest-text">' + item.text + '</span>';
            container.appendChild(div);
        });
        // 更新日期标记
        var titlePanel = document.querySelector('.ai-digest .panel-title');
        if (titlePanel) {
            titlePanel.innerHTML = '🤖 AI投研日报摘要 <span style="font-size:0.65rem;color:#888;margin-left:8px;">' + (data.date || '') + '</span>';
        }
    })
    .catch(function(err) {
        console.error('AI摘要加载失败:', err);
        // 加载失败时保留默认静态内容
    });
}

// DOMContentLoaded 时调用
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', renderAIDigest);
} else {
    renderAIDigest();
}
