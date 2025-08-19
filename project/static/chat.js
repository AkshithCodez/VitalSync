document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatWindow = document.getElementById('chat-window');
    const chatToggleButton = document.getElementById('chat-toggle-button');
    const chatWidgetContainer = document.getElementById('chat-widget-container');

    if (chatToggleButton && chatWidgetContainer) {
        chatToggleButton.addEventListener('click', () => {
            chatWidgetContainer.classList.toggle('hidden');
        });
    }

    if (chatForm) {
        chatForm.addEventListener('submit', async function(event) {
            event.preventDefault();
            const userMessage = chatInput.value.trim();
            if (userMessage === "") return;

            appendMessage(userMessage, 'user-message');
            chatInput.value = "";
            appendMessage("...", 'ai-message', true);

            try {
                const chatUrl = chatForm.dataset.chatUrl;
                const response = await fetch(chatUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: userMessage })
                });
                if (!response.ok) throw new Error('Network response was not ok');
                
                const data = await response.json();
                removeTypingIndicator();
                appendMessage(data.reply, 'ai-message');
            } catch (error) {
                removeTypingIndicator();
                appendMessage("Sorry, I'm having trouble connecting.", 'ai-message');
            }
        });
    }

    function appendMessage(text, className, isTyping = false) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('chat-message', className);
        const messageP = document.createElement('p');
        messageP.textContent = text;
        if (isTyping) {
            messageDiv.id = 'typing-indicator';
            messageP.classList.add('typing-animation');
        }
        messageDiv.appendChild(messageP);
        chatWindow.appendChild(messageDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    function removeTypingIndicator() {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) typingIndicator.remove();
    }
});