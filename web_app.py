from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import json
import os
import requests
import hashlib
import base64
from datetime import datetime
from typing import List, Dict, Optional

from chatbot import ChatBot
from config import ChatConfig

# 创建FastAPI应用
app = FastAPI(title="Chat Agent", description="智能聊天助手", version="1.0.0")

# 配置静态文件和模板
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 全局聊天机器人实例
chat_bot = None

# 请求和响应模型
class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    timestamp: str
    audio_url: Optional[str] = None  # 语音文件URL

class ChatHistory(BaseModel):
    messages: List[Dict[str, str]]

def get_chat_bot():
    """获取聊天机器人实例（单例模式）"""
    global chat_bot
    if chat_bot is None:
        chat_bot = ChatBot()
    return chat_bot

def synthesize_speech(text, language="zh"):
    """语音合成功能"""
    try:
        # 创建音频文件目录
        audio_dir = "static/audio"
        os.makedirs(audio_dir, exist_ok=True)
        
        # 生成文件名（基于文本内容的哈希值）
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        output_file = f"{audio_dir}/speech_{text_hash}.wav"
        
        # 如果文件已存在，直接返回
        if os.path.exists(output_file):
            return f"/static/audio/speech_{text_hash}.wav"
        
        # 调用语音合成API
        url = "http://localhost:8000/tts"
        payload = {
            "text": text,
            "text_language": language,
            "temperature": 0.6,
            "speed": 1.0,
            "top_k": 20,
            "top_p": 0.6
        }
        
        response = requests.post(url, json=payload, timeout=60)
        
        if response.status_code == 200:
            with open(output_file, "wb") as f:
                f.write(response.content)
            return f"/static/audio/speech_{text_hash}.wav"
        else:
            print(f"语音合成失败: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"语音合成服务连接失败: {e}")
        return None
    except Exception as e:
        print(f"语音合成发生错误: {e}")
        return None

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """主页面"""
    return templates.TemplateResponse("chat.html", {"request": request})

@app.post("/api/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    """处理聊天消息"""
    try:
        bot = get_chat_bot()
        
        # 检查特殊命令
        user_input = message.message.strip()
        response = bot.process_message(user_input)
        
        # 生成语音
        audio_url = synthesize_speech(response)
        
        return ChatResponse(
            response=response,
            timestamp=datetime.now().isoformat(),
            audio_url=audio_url
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理消息时发生错误: {str(e)}")

@app.get("/api/history", response_model=ChatHistory)
async def get_history():
    """获取聊天历史"""
    try:
        bot = get_chat_bot()
        messages = []
        
        for item in bot.chat_history:
            messages.append({
                "type": "user",
                "content": item["user"],
                "timestamp": item.get("timestamp", "")
            })
            messages.append({
                "type": "bot",
                "content": item["bot"],
                "timestamp": item.get("timestamp", "")
            })
        
        return ChatHistory(messages=messages)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取历史记录时发生错误: {str(e)}")

@app.delete("/api/history")
async def clear_history():
    """清除聊天历史"""
    try:
        bot = get_chat_bot()
        bot.clear_history()
        return JSONResponse(content={"message": "聊天历史已清除"})
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除历史记录时发生错误: {str(e)}")

@app.get("/api/status")
async def get_status():
    """获取系统状态"""
    try:
        bot = get_chat_bot()
        
        # 检查TTS服务状态
        tts_available = False
        try:
            tts_response = requests.get("http://localhost:8000/health", timeout=5)
            tts_available = tts_response.status_code == 200
        except:
            tts_available = False
        
        return {
            "status": "running",
            "bot_name": bot.config.BOT_NAME,
            "version": bot.config.VERSION,
            "llm_available": bot.llm_client.is_available if bot.llm_client else False,
            "tts_available": tts_available,
            "chat_history_count": len(bot.chat_history)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取状态时发生错误: {str(e)}")

@app.post("/api/tts")
async def text_to_speech(request: dict):
    """独立的语音合成API端点"""
    try:
        text = request.get("text", "")
        language = request.get("language", "zh")
        
        if not text:
            raise HTTPException(status_code=400, detail="文本内容不能为空")
        
        audio_url = synthesize_speech(text, language)
        
        if audio_url:
            return {"audio_url": audio_url, "success": True}
        else:
            return {"error": "语音合成失败", "success": False}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"语音合成时发生错误: {str(e)}")

if __name__ == "__main__":
    # 确保必要的目录存在
    os.makedirs("static", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    
    # 启动应用
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)
