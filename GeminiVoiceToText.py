import asyncio
import base64
import json
import pyaudio
import websockets
import os
from dotenv import load_dotenv
import tkinter as tk
from tkinter import ttk

class GeminiVoiceToText:
    def __init__(self):
        # 加载环境变量
        load_dotenv()
        self.api_key = os.getenv('GEMINI_API_KEY')
        self.model = "gemini-2.0-flash-exp"
        self.uri = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent?key={self.api_key}"

        # 音频设置
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.CHUNK = 256
        self.RATE = 16000

        # API 配置
        self.config = {
            "setup": {
                "model": f"models/{self.model}",
                "generation_config": {
                    "response_modalities": ["TEXT"]
                },
            }
        }

        # 系统指令
        self.system_instruction = {
            "client_content": {
                "turns": [
                    {
                        "parts": [
                            {
                                "text": """🎯 实时语音翻译助手

作为专业的实时语音翻译助手,我将按以下规则工作:

📝 英语语音处理
• 准确转写英语语音内容
• 提供流畅自然的中文翻译
• 按如下格式输出:
  英文原文
  翻译：中文译文

✨ 翻译要求
• 保持原意和语气
• 使用地道现代的中文表达
• 准确翻译专有名词和技术术语
• 传达原文的情感色彩

📋 输出示例:
This is an example sentence.
翻译：这是一个示例句子。

📌 补充说明
• 遇到不清晰语音时,提供最合理的理解
• 技术术语优先使用常见中文译法
• 根据场合调整翻译的正式程度"""
                            }
                        ],
                        "role": "user"
                    }
                ],
                "turn_complete": True
            }
        }

        # 创建 UI
        self.window = TranslatorWindow()

    async def start(self):
        self.ws = await websockets.connect(self.uri)
        
        # 发送初始配置
        await self.ws.send(json.dumps(self.config))
        await self.ws.recv()

        # 发送系统指令
        await self.ws.send(json.dumps(self.system_instruction))
        await self.ws.recv()
        print("已连接到 Gemini")

        # 同时运行音频发送和响应接收
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.send_user_audio())
            tg.create_task(self.receive_text_responses())

    async def send_user_audio(self):
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK
        )

        try:
            while True:
                data = await asyncio.to_thread(stream.read, self.CHUNK)
                audio_data = base64.b64encode(data).decode()
                
                message = {
                    "realtime_input": {
                        "media_chunks": [{
                            "data": audio_data,
                            "mime_type": "audio/pcm"
                        }]
                    }
                }
                await self.ws.send(json.dumps(message))
        except Exception as e:
            print(f"音频流错误: {e}")
            stream.stop_stream()
            stream.close()
            audio.terminate()

    async def receive_text_responses(self):
        current_response = ""
        
        try:
            async for msg in self.ws:
                response = json.loads(msg)
                if 'serverContent' in response:
                    if 'modelTurn' in response['serverContent']:
                        text = response['serverContent']['modelTurn']['parts'][0].get('text', '')
                        if text:
                            self.window.add_message(text)
                    
                    if response['serverContent'].get('turnComplete'):
                        current_response = ""
        except Exception as e:
            print(f"接收响应错误: {e}")

class TranslatorWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("实时翻译")
        
        # 设置窗口属���
        self.root.attributes('-alpha', 0.8)
        self.root.attributes('-topmost', True)
        self.root.overrideredirect(True)
        
        # 创建标题栏框架
        self.title_bar = tk.Frame(
            self.root,
            bg='#2D2D2D',  # 深色背景
            height=30
        )
        self.title_bar.pack(fill=tk.X, side=tk.TOP)
        self.title_bar.pack_propagate(False)  # 固定高度
        
        # 创建标题文本
        self.title_label = tk.Label(
            self.title_bar,
            text="实时翻译",
            bg='#2D2D2D',
            fg='#FFFFFF',
            font=('Microsoft YaHei UI', 10)
        )
        self.title_label.pack(side=tk.LEFT, padx=10)
        
        # 创建关闭按钮
        self.close_button = tk.Button(
            self.title_bar,
            text="×",
            command=self.close_window,
            bg='#2D2D2D',
            fg='#FFFFFF',
            font=('Microsoft YaHei UI', 12, 'bold'),
            bd=0,
            padx=10,
            activebackground='#E81123',  # 鼠标悬停时的颜色
            activeforeground='#FFFFFF'
        )
        self.close_button.pack(side=tk.RIGHT)
        
        # 创建主界面框架
        self.frame = ttk.Frame(self.root)
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        # 修改文本区域的样式
        self.text_area = tk.Text(
            self.frame,
            wrap=tk.WORD,
            bg='#1E1E1E',
            fg='#FFFFFF',
            font=('Microsoft YaHei UI', 12),
            padx=10,
            pady=10,
            spacing1=5,
            spacing2=2,
        )
        self.text_area.pack(fill=tk.BOTH, expand=True)
        
        # 拖动功能
        self.title_bar.bind('<Button-1>', self.start_move)
        self.title_bar.bind('<B1-Motion>', self.do_move)
        self.title_label.bind('<Button-1>', self.start_move)
        self.title_label.bind('<B1-Motion>', self.do_move)
        
        self.root.geometry('400x300+100+100')
        
        self.messages = []
        self.max_messages = 10

    def close_window(self):
        """关闭窗口并退出程序"""
        self.root.quit()
        self.root.destroy()
        os._exit(0)  # 强制退出程序

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def add_message(self, message):
        # 如果是新的完整消息，就添加到表中
        if message.strip().startswith(('mechanism', 'This', 'I', 'The')):  # 英文句子的常见开头
            self.messages.append(message)
            if len(self.messages) > self.max_messages:
                self.messages.pop(0)
            # 清空并重新显示所有消息
            self.text_area.delete('1.0', tk.END)
            for msg in self.messages:
                self.text_area.insert(tk.END, msg)
        else:
            # 如果是消息的后续部分，直接追加到最后
            self.text_area.insert(tk.END, message)
        
        # 滚动到最新内容
        self.text_area.see(tk.END)
        
        # 添加标签样式
        self.text_area.tag_add("english", "1.0", "end")
        self.text_area.tag_config(
            "english",
            font=('Microsoft YaHei UI', 12),
            spacing1=10,
            spacing2=5
        )

    def start(self):
        self.root.mainloop()

def main():
    client = GeminiVoiceToText()
    
    # 创建新的事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # 创建并启动后台任务
    async def run_client():
        try:
            await client.start()
        except Exception as e:
            print(f"客户端运行错误: {e}")
    
    # 在新线程中运行 WebSocket 连接
    import threading
    def run_async():
        loop.run_until_complete(run_client())
    
    websocket_thread = threading.Thread(target=run_async)
    websocket_thread.daemon = True
    websocket_thread.start()
    
    # 在主线程中运行 UI
    try:
        client.window.start()
    except KeyboardInterrupt:
        print("程序终止")
    finally:
        loop.stop()
        loop.close()

if __name__ == "__main__":
    main()
