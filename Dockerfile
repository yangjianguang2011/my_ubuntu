# 使用更小的基础镜像
FROM ubuntu:22.04

# 1. 设置时区和镜像源（合并操作）
ENV TZ=Asia/Shanghai

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
     cp /etc/apt/sources.list /etc/apt/sources.list.bak && \
     echo "deb http://mirrors.ustc.edu.cn/ubuntu/ jammy main restricted universe multiverse" > /etc/apt/sources.list && \
     echo "deb http://mirrors.ustc.edu.cn/ubuntu/ jammy-updates main restricted universe multiverse" >> /etc/apt/sources.list && \
     echo "deb http://mirrors.ustc.edu.cn/ubuntu/ jammy-backports main restricted universe multiverse" >> /etc/apt/sources.list && \
     echo "deb http://mirrors.ustc.edu.cn/ubuntu/ jammy-security main restricted universe multiverse" >> /etc/apt/sources.list && \
     rm -rf /var/lib/apt/lists/*

# 2. 一次性安装所有系统依赖（减少层数）
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    tzdata \
    python3 \
    python3-pip \
    cron \
    git \
    curl \
    vim \
    wget \
    gnupg2 \
    ca-certificates \
    lsb-release \
    xz-utils \
    unzip \
    openssh-server \
    sudo \
    lsof \
    libgomp1 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    nginx=1.18.0* \
    supervisor \
    # OpenClaw 浏览器依赖
    xvfb \
    libx11-xcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxi6 \
    libxtst6 \
    libnss3 \
    libnspr4 \
    && rm -rf /var/lib/apt/lists/*

# 3. 安装 Node.js 和 OpenClaw
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y nodejs
RUN npm install -g openclaw@latest

# 4. 安装 Chrome 相关
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    pip3 install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple webdriver-manager && \
    python3 -c "from webdriver_manager.chrome import ChromeDriverManager; import subprocess; subprocess.run(['cp', ChromeDriverManager().install(), '/usr/local/bin/chromedriver']); subprocess.run(['chmod', '+x', '/usr/local/bin/chromedriver'])"

# 5. 安装 Tesseract OCR（用于图片文字识别，可选）
#RUN apt-get update && apt-get install -y tesseract-ocr tesseract-ocr-chi-sim
#RUN pip3 install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
#    paddlepaddle==3.2.2 \
#    Pillow \
#    paddleocr

# 6. SSH Config
RUN mkdir -p /var/run/sshd && \
    ssh-keygen -A && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#Port 22/Port 4422/' /etc/ssh/sshd_config && \
    echo 'root:rootpassword' | chpasswd && \
    useradd -m -s /bin/bash ubuntu && \
    echo 'ubuntu:ubuntupass' | chpasswd && \
    usermod -aG sudo ubuntu

# 7. 安装 Python 依赖
# Stock Monitor
COPY ./apps/stock_monitor/requirements.txt /tmp/stock_requirements.txt
RUN pip3 install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r /tmp/stock_requirements.txt && rm /tmp/stock_requirements.txt

# NEWS
COPY ./apps/news/requirements.txt /tmp/news_requirements.txt
RUN pip3 install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r /tmp/news_requirements.txt && rm /tmp/news_requirements.txt

# 8. 复制配置文件（应用配置放到 /root/apps 下）
COPY ./apps/config.ini /root/apps/config.ini
COPY ./apps/config.sh /root/apps/config.sh
COPY ./apps/config.py /root/apps/config.py
RUN chmod +x /root/apps/config.sh

# 9. 复制代码文件
# Nginx 配置（系统配置）
COPY ./configs/default /etc/nginx/sites-enabled/default
COPY ./configs/nginx.conf /etc/nginx/nginx.conf

# 应用模块
COPY ./apps/iptv /root/apps/iptv
COPY ./apps/news /root/apps/news
COPY ./apps/stock_monitor /root/apps/stock_monitor
COPY ./apps/crawlers /root/apps/crawlers

# 10. 创建目录结构
RUN mkdir -p /data/xueqiu_data && \
    mkdir -p /data/analyst_data && \
    mkdir -p /data/stock_monitor_data/database && \
    mkdir -p /var/log/cron && \
    mkdir -p /var/log/supervisor && \
    mkdir -p /var/log/nginx && \
    mkdir -p /var/log/ssh && \
    mkdir -p /var/log/stock_monitor && \
    mkdir -p /var/log/openclaw && \
    mkdir -p /var/run/supervisor && \
    mkdir -p /root/.openclaw/workspace

# 11. 设置权限
RUN chmod +x \
    /root/apps/iptv/download_m3u.py \
    /root/apps/news/run.sh \
    /root/apps/crawlers/eastmoney/run_eastmoney.sh \
    /root/apps/crawlers/xueqiu/run_xueqiu.sh

# 12. 配置 Cron 作业
COPY <<EOF /etc/cron.d/myjobs
0 */8 * * * root cd /root/apps/news && /bin/bash run.sh >> /var/log/cron/news.log 2>&1
5 23 * * * root cd /root/apps/iptv && /usr/bin/python3 download_m3u.py >> /var/log/cron/iptv.log 2>&1
10 23 * * * root cd /root/apps/crawlers/xueqiu && /bin/bash run_xueqiu.sh >> /var/log/cron/xueqiu.log 2>&1
40 23 * * * root cd /root/apps/crawlers/eastmoney && /bin/bash run_eastmoney.sh >> /var/log/cron/eastmoney.log 2>&1
EOF
RUN chmod 0644 /etc/cron.d/myjobs

# 14. 暴露端口（添加 OpenClaw 端口）
EXPOSE 80 4422 5001 38789

# 15. 复制启动脚本
COPY start_container.sh /start_container.sh
RUN chmod +x /start_container.sh

# 启动命令 - 使用简单服务管理脚本
CMD ["/start_container.sh"]
