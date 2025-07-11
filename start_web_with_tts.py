#!/usr/bin/env python3
"""
银月 AI 聊天机器人 - Web界面启动脚本 (支持语音合成)

这个脚本启动一个Web服务器，提供类似ChatGPT的聊天界面，支持语音合成功能。

使用方法:
1. 确保已安装所有依赖: pip install -r requirements.txt
2. 配置环境变量 (API_KEY等)
3. 启动TTS语音服务 (可选，默认端口8000)
4. 运行此脚本: python start_web_with_tts.py
5. 在浏览器中访问: http://localhost:8001
"""

import os
import sys
import requests
import uvicorn

def check_dependencies():
    """检查必要的依赖是否已安装"""
    required_packages = {
        'fastapi': 'FastAPI',
        'uvicorn': 'Uvicorn', 
        'jinja2': 'Jinja2',
        'requests': 'Requests'
    }
    
    missing = []
    for package, name in required_packages.items():
        try:
            __import__(package)
            print(f"✅ {name} 已安装")
        except ImportError:
            missing.append(package)
            print(f"❌ {name} 未安装")
    
    if missing:
        print(f"\n请安装缺失的包: pip install {' '.join(missing)}")
        return False
    
    return True

def check_environment():
    """检查环境配置"""
    from config import ChatConfig
    config = ChatConfig()
    
    if not config.API_KEY:
        print("⚠️  警告: 未设置 OPENAI_API_KEY 环境变量")
        print("   请在 .env 文件中设置或通过环境变量设置")
        return False
    
    print("✅ 环境配置检查通过")
    return True

def check_tts_service():
    """检查TTS语音服务状态"""
    try:
        response = requests.get("http://localhost:8000/status", timeout=3)
        if response.status_code == 200:
            print("✅ TTS语音服务已启动")
            return True
    except:
        pass
    
    print("⚠️  TTS语音服务未启动")
    print("   语音功能将不可用，但聊天功能仍然正常")
    print("   如需启用语音，请确保TTS服务在 http://localhost:8000 运行")
    return False

def main():
    """主函数"""
    print("🚀 启动银月 AI 聊天机器人 Web 界面 (支持语音)...")
    print("=" * 60)
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 检查环境
    if not check_environment():
        print("🔧 请配置环境变量后重试")
        sys.exit(1)
    
    # 检查TTS服务 (非必需)
    check_tts_service()
    
    # 确保必要的目录存在
    os.makedirs("static/audio", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    
    print("\n🌐 Web服务器启动中...")
    print("📱 访问地址: http://localhost:8001")
    print("🛑 按 Ctrl+C 停止服务器")
    print("🎤 语音功能需要TTS服务在端口8000运行")
    print("💬 即使没有TTS服务，聊天功能也能正常使用\n")
    
    try:
        # 启动FastAPI应用
        uvicorn.run(
            "web_app:app",
            host="0.0.0.0",
            port=8001,  # 使用8001端口避免与TTS服务冲突
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n\n👋 服务器已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
