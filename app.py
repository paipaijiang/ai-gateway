import os
from flask import Flask, request, jsonify
from zhipuai import ZhipuAI
import requests
import json

app = Flask(__name__)

# 获取智谱 AI Key
client = ZhipuAI(api_key=os.environ.get("ZHIPU_AI_KEY"))

def get_recent_logs(service_name):
    log_map = {
        "ai_assistant": "/var/log/nginx/aiAssistant/",
        "kodbox": "/var/log/nginx/kodbox/"
    }
    
    log_path = log_map.get(service_name)
    print(f">>> 正在尝试读取服务: {service_name}, 路径: {log_path}", flush=True) 

    if not log_path or not os.path.exists(log_path):
        return "未能定位日志目录。"

    # 精准匹配文件名
    if service_name == "ai_assistant":
        files_to_read = ["ai_access_ssl.log", "ai_error_ssl.log"]
    else:
        files_to_read = ["kodbox_access_ssl.log", "kodbox_error_ssl.log"]

    combined_logs = []
    for file_name in files_to_read:
        full_path = os.path.join(log_path, file_name)
        if os.path.exists(full_path):
            try:
                with open(full_path, 'r') as f:
                    lines = f.readlines()
                    # 取最后 15 行，并过滤掉空行
                    last_lines = [l.strip() for l in lines[-15:] if l.strip()]
                    combined_logs.append(f"[{file_name}]")
                    combined_logs.extend(last_lines)
            except Exception as e:
                combined_logs.append(f"读取 {file_name} 报错: {e}")
        else:
            combined_logs.append(f"文件 {file_name} 不存在")

    return "\n".join(combined_logs) if combined_logs else "日志文件为空"


def send_dingtalk(content):
    # 记得替换成你真实的 Webhook 地址
    token = "ca027064e20b25294996fef6dd75a5cf80ca79a66051820e56bd54f622ce4e66"
    url = f"https://oapi.dingtalk.com/robot/send?access_token={token}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": "AI 运维诊断报告",
            "text": f"## 🚨 告警诊断已送达\n\n**分析结果：**\n\n{content}\n\n"
        }
    }
    try:
        res = requests.post(url, json=payload, headers=headers)
        print(f">>> 钉钉推送状态: {res.status_code}", flush=True)
    except Exception as e:
        print(f">>> 钉钉推送失败: {e}", flush=True)

@app.route('/alert', methods=['POST'])  # 注意：这里需要加上 @ 符号
def handle_alert():
    # 1. 更加健壮的数据获取
    data = request.get_json() 
    if not data:
        return "Empty data", 400
    print(f">>> 收到 Webhook，状态: {data.get('status')}", flush=True)

    alerts = data.get('alerts', [])
    
    for alert in alerts:
        status = alert.get('status')
        service = alert.get('labels', {}).get('service', '通用业务')
        instance = alert.get('labels', {}).get('instance', '未知节点')

        # --- 1. 如果是故障恢复通知 ---
        if status == 'resolved':
            resolved_msg = (
                f"### ✅ 业务恢复通知\n"
                f"**监控业务**：{service}\n"
                f"**所在节点**：{instance}\n\n"
                f"**当前状态**：服务已恢复正常运行。AI 诊断链路已自动挂起。"
            )
            print(f">>> 业务 {service} 已恢复，跳过 AI 诊断", flush=True)
            send_dingtalk(resolved_msg)
            continue # 处理完恢复，跳到下一个告警

        # --- 2. 如果是故障触发通知 (Firing) ---
        # 注意：下面的每一行都要和上面的 if 对齐！
        summary = alert.get('annotations', {}).get('summary', '系统异常')
        description = alert.get('annotations', {}).get('description', '暂无详细描述')
        
        # 1. 抓取日志
        context_logs = get_recent_logs(service)
            
        # 2. 拼接 Prompt
        prompt = f"系统收到告警: {summary}\n"
        prompt += f"故障描述: {description}\n"
        prompt += f"现场证据: {context_logs}\n"
        prompt += "请分析故障原因并给出修复建议。"
        
        # 3. 调用智谱 AI
        try:
            response = client.chat.completions.create(
                model="glm-4",
                messages=[
                    {"role": "system", "content": "你是一个资深的 SRE 运维专家..."},
                    {"role": "user", "content": prompt}
                ]
            )           


            ai_result = response.choices[0].message.content
            
            # 拼装带红色警示的钉钉消息
            firing_msg = (
                f"### 🚨 故障诊断报告 ({service})\n\n"
                f"**告警摘要**：{summary}\n"
                f"**AI 分析建议**：\n\n{ai_result}"
            )
            send_dingtalk(firing_msg)
        except Exception as e:
            print(f"AI 调用失败: {e}", flush=True)
        
    return jsonify({"status": "success"}), 200        

if __name__ == '__main__':
    # 记得在生产环境开启 debug=False
    app.run(host='0.0.0.0', port=5000)
