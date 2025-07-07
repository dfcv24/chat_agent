from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
import json
import os
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

class ChatHistory(BaseModel):
    messages: List[Dict[str, str]]

def get_chat_bot():
    """获取聊天机器人实例（单例模式）"""
    global chat_bot
    if chat_bot is None:
        chat_bot = ChatBot()
    return chat_bot

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
        
        if user_input.lower() in bot.config.EXIT_COMMANDS:
            return ChatResponse(
                response="再见！感谢使用聊天助手～👋",
                timestamp=datetime.now().isoformat()
            )
        
        if user_input.lower() in bot.config.CLEAR_COMMANDS:
            bot.clear_history()
            return ChatResponse(
                response="✅ 聊天历史已清除",
                timestamp=datetime.now().isoformat()
            )
        
        if user_input.lower() in bot.config.HELP_COMMANDS:
            help_text = f"""
🤖 {bot.config.BOT_NAME} 帮助信息

📝 基本使用:
   直接输入你的问题或想说的话

🔧 特殊命令:
   清除历史/清空/clear - 清除聊天历史
   帮助/help/命令 - 显示此帮助信息

💡 提示:
   - 我会记住最近的对话内容
   - 你可以随时询问任何问题
   - 输入要清楚明确，我会尽力帮助你

版本: {bot.config.VERSION}
            """
            return ChatResponse(
                response=help_text,
                timestamp=datetime.now().isoformat()
            )
        
        # 获取AI回复
        response = bot.get_response(user_input)
        
        # 保存到历史记录
        bot.add_to_history(user_input, response)
        bot.save_chat_history()
        
        # 处理知识提取（如果启用）
        if bot.config.ENABLE_KNOWLEDGE_LEARNING and bot.last_question_context:
            extracted_info = bot.knowledge_manager.extract_info_from_response(
                user_input, bot.last_question_context
            )
            
            if extracted_info:
                updated = bot.knowledge_manager.update_knowledge(extracted_info)
                if updated:
                    response += "\n\n✨ 我记住了关于你的新信息～"
        
        # 重置问题上下文
        bot.last_question_context = ""
        
        return ChatResponse(
            response=response,
            timestamp=datetime.now().isoformat()
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
        return {
            "status": "running",
            "bot_name": bot.config.BOT_NAME,
            "version": bot.config.VERSION,
            "llm_available": bot.llm_client.is_available if bot.llm_client else False,
            "knowledge_learning_enabled": bot.config.ENABLE_KNOWLEDGE_LEARNING,
            "chat_history_count": len(bot.chat_history)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取状态时发生错误: {str(e)}")

if __name__ == "__main__":
    # 确保必要的目录存在
    os.makedirs("static", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    
    # 启动应用
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
