# 1. 使用官方极简的 Python 镜像作为基础
FROM python:3.9-slim

# 2. 设置容器内的工作目录
WORKDIR /app

# 3. 将当前目录下的所有文件复制到容器的 /app 目录下
COPY . /app

# 4. 在容器内安装 Python 依赖（这就是“安装过程”）
# 使用清华源加速，防止国内 ECS 访问过慢
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple flask zhipuai sniffio httpx requests
# 5. 容器启动时运行脚本
CMD ["python", "app.py"]
