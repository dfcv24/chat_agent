from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import os
import requests
import hashlib
from datetime import datetime
from typing import List, Dict, Optional

from chatbot import ChatBot
from event_system import ChatEventSystem, EventType, ChatEvent

# 创建FastAPI应用
app = FastAPI(title="Chat Agent", description="智能聊天助手", version="1.0.0")

# 配置静态文件和模板
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 全局聊天机器人实例和事件系统
chat_bot = None
event_system = None
active_connections: List[WebSocket] = []

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
    global chat_bot, event_system
    if chat_bot is None:
        chat_bot = ChatBot()
        event_system = ChatEventSystem(chat_bot)
        
        # 订阅事件并广播给所有WebSocket连接
        event_system.event_queue.subscribe(EventType.BOT_OUTPUT, broadcast_bot_message)
        event_system.event_queue.subscribe(EventType.BOT_THINKING, broadcast_thinking)
        event_system.event_queue.subscribe(EventType.SYSTEM_MESSAGE, broadcast_system_message)
        event_system.event_queue.subscribe(EventType.ERROR, broadcast_error)
        
        event_system.start()
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

# WebSocket连接管理
async def add_connection(websocket: WebSocket):
    """添加WebSocket连接"""
    active_connections.append(websocket)

async def remove_connection(websocket: WebSocket):
    """移除WebSocket连接"""
    if websocket in active_connections:
        active_connections.remove(websocket)

async def broadcast_to_all(message_data: dict):
    """向所有活跃连接广播消息"""
    if not active_connections:
        return
    
    # 创建需要移除的连接列表
    disconnected = []
    
    for connection in active_connections:
        try:
            await connection.send_json(message_data)
        except Exception:
            disconnected.append(connection)
    
    # 移除断开的连接
    for conn in disconnected:
        await remove_connection(conn)

# 事件广播函数
async def broadcast_bot_message(event: ChatEvent):
    """广播机器人消息"""
    # 生成语音
    audio_url = synthesize_speech(event.content) if event.content else None
    
    message_data = {
        "type": "bot_message",
        "content": event.content,
        "timestamp": event.timestamp.isoformat(),
        "event_id": event.event_id,
        "audio_url": audio_url
    }
    await broadcast_to_all(message_data)

async def broadcast_thinking(event: ChatEvent):
    """广播思考状态"""
    message_data = {
        "type": "thinking",
        "content": event.content,
        "timestamp": event.timestamp.isoformat(),
        "event_id": event.event_id
    }
    await broadcast_to_all(message_data)

async def broadcast_system_message(event: ChatEvent):
    """广播系统消息"""
    message_data = {
        "type": "system_message",
        "content": event.content,
        "timestamp": event.timestamp.isoformat(),
        "event_id": event.event_id
    }
    await broadcast_to_all(message_data)

async def broadcast_error(event: ChatEvent):
    """广播错误消息"""
    message_data = {
        "type": "error",
        "content": event.content,
        "timestamp": event.timestamp.isoformat(),
        "event_id": event.event_id
    }
    await broadcast_to_all(message_data)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """主页面 - 实时版本"""
    return templates.TemplateResponse("chat_realtime.html", {"request": request})

@app.get("/classic", response_class=HTMLResponse)
async def read_classic(request: Request):
    """经典版本页面"""
    return templates.TemplateResponse("chat.html", {"request": request})

@app.post("/api/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    """处理聊天消息（保持向后兼容）"""
    try:
        # 获取聊天机器人和事件系统
        bot = get_chat_bot()
        
        # 检查特殊命令
        user_input = message.message.strip()
        
        # 通过事件系统处理（但同步等待结果）
        if user_input.lower() in ['/help', 'help', '帮助']:
            response = "这里是帮助信息..."
        elif user_input.lower() in ['/clear', 'clear', '清除']:
            bot.clear_history()
            response = "聊天历史已清除"
        else:
            response = bot.get_response(user_input)
        
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

# 新入口
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket端点 - 实现实时双向通信"""
    await websocket.accept()
    await add_connection(websocket)
    
    # 获取事件系统
    get_chat_bot()  # 确保事件系统已初始化
    
    try:
        # 发送欢迎消息
        await event_system.emit_system_message("🎉 欢迎使用智能聊天助手！")
        
        while True:
            # 接收用户消息
            data = await websocket.receive_json()
            
            if data.get("type") == "user_message":
                user_input = data.get("content", "").strip()
                if user_input:
                    # 通过事件系统处理用户输入
                    await event_system.emit_user_input(user_input)
            
            elif data.get("type") == "ping":
                # 心跳检测
                await websocket.send_json({"type": "pong"})
            
            elif data.get("type") == "set_auto_output":
                # 设置主动输出
                enabled = data.get("enabled", True)
                event_system.set_auto_output(enabled)
                await event_system.emit_system_message(
                    f"主动输出已{'启用' if enabled else '禁用'}"
                )
            
            elif data.get("type") == "clear_history":
                # 清除历史
                chat_bot.clear_history()
                await event_system.emit_system_message("聊天历史已清除")
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket错误: {e}")
    finally:
        await remove_connection(websocket)

@app.post("/api/event/auto_output")
async def set_auto_output(request: dict):
    """设置主动输出"""
    try:
        enabled = request.get("enabled", True)
        get_chat_bot()  # 确保系统已初始化
        event_system.set_auto_output(enabled)
        
        return {"message": f"主动输出已{'启用' if enabled else '禁用'}", "enabled": enabled}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"设置主动输出时发生错误: {str(e)}")

@app.post("/api/event/trigger_auto")
async def trigger_auto_message():
    """手动触发主动输出"""
    try:
        get_chat_bot()  # 确保系统已初始化
        message = await event_system._generate_auto_message()
        if message:
            await event_system.emit_bot_output(message)
            return {"message": "已触发主动输出", "content": message}
        else:
            return {"message": "暂无主动输出内容"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"触发主动输出时发生错误: {str(e)}")

@app.get("/api/event/status")
async def get_event_status():
    """获取事件系统状态"""
    try:
        get_chat_bot()  # 确保系统已初始化
        
        return {
            "running": event_system.running,
            "auto_output_enabled": event_system.auto_output_enabled,
            "idle_threshold": event_system.idle_threshold,
            "active_connections": len(active_connections),
            "last_user_input": event_system.last_user_input_time.isoformat() if event_system.last_user_input_time else None,
            "queue_empty": event_system.event_queue.empty()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取事件状态时发生错误: {str(e)}")

@app.post("/api/event/system_message")
async def send_system_message(request: dict):
    """发送系统消息"""
    try:
        content = request.get("content", "")
        if not content:
            raise HTTPException(status_code=400, detail="消息内容不能为空")
        
        get_chat_bot()  # 确保系统已初始化
        await event_system.emit_system_message(content)
        
        return {"message": "系统消息已发送", "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送系统消息时发生错误: {str(e)}")

if __name__ == "__main__":
    # 确保必要的目录存在
    os.makedirs("static", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    
    # 启动应用
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)
