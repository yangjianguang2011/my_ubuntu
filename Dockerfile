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
    && rm -rf /var/lib/apt/lists/*

# 3. 提前安装 PaddleOCR 及其依赖
#RUN pip3 install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
#    paddlepaddle==3.2.2 \
#    Pillow \
#    paddleocr

# 4. 安装 Chrome 相关
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    pip3 install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple webdriver-manager && \
    python3 -c "from webdriver_manager.chrome import ChromeDriverManager; import subprocess; subprocess.run(['cp', ChromeDriverManager().install(), '/usr/local/bin/chromedriver']); subprocess.run(['chmod', '+x', '/usr/local/bin/chromedriver'])"

# 5. SSH Config
RUN mkdir -p /var/run/sshd && \
    ssh-keygen -A && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#Port 22/Port 4422/' /etc/ssh/sshd_config && \
    echo 'root:rootpassword' | chpasswd && \
    useradd -m -s /bin/bash ubuntu && \
    echo 'ubuntu:ubuntupass' | chpasswd && \
    usermod -aG sudo ubuntu

# 6. 安装 Python 依赖
# Stock Monitor
COPY ./stock_monitor/requirements.txt /tmp/stock_requirements.txt
RUN pip3 install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r /tmp/stock_requirements.txt && rm /tmp/stock_requirements.txt

# NEWS
COPY ./news/requirements.txt /tmp/news_requirements.txt
RUN pip3 install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r /tmp/news_requirements.txt && rm /tmp/news_requirements.txt

# 6.5 复制配置文件
COPY config.ini /root/config.ini
COPY config.sh /root/config.sh
COPY config.py /root/config.py
RUN chmod +x /root/config.sh

# 7. 复制代码文件
# Nginx 配置
COPY default /etc/nginx/sites-enabled/default
COPY nginx.conf /etc/nginx/nginx.conf

# IPTV
COPY ./iptv /root/iptv

# NEWS
COPY ./news /root/news

# Stock Monitor
COPY ./stock_monitor /root/stock_monitor

# Crawlers
COPY ./crawlers /root/crawlers

# 8. 创建目录结构
RUN mkdir -p /data/xueqiu_data && \
    mkdir -p /data/analyst_data && \
    mkdir -p /data/stock_monitor_data/database && \
    mkdir -p /var/log/cron && \
    mkdir -p /var/log/supervisor && \
    mkdir -p /var/log/nginx && \
    mkdir -p /var/log/ssh && \
    mkdir -p /var/log/stock_monitor && \
    mkdir -p /var/run/supervisor

# 9. 设置权限
RUN chmod +x \
    /root/iptv/download_m3u.py \
    /root/news/run.sh \
    /root/crawlers/spiders/run_eastmoney.sh \
    /root/crawlers/spiders/run_xueqiu.sh

# 10. 配置 Cron 作业
COPY <<EOF /etc/cron.d/myjobs
0 */8 * * * root cd /root/news && /bin/bash run.sh >> /var/log/cron/news.log 2>&1
5 23 * * * root cd /root/iptv && /usr/bin/python3 download_m3u.py >> /var/log/cron/iptv.log 2>&1
10 23 * * * root cd /root/crawlers/spiders && /bin/bash run_xueqiu.sh >> /var/log/cron/xueqiu.log 2>&1
40 23 * * * root cd /root/crawlers/spiders && /bin/bash run_eastmoney.sh >> /var/log/cron/eastmoney.log 2>&1
EOF
RUN chmod 0644 /etc/cron.d/myjobs

# 11. 复制 Supervisord 配置
COPY supervisord.conf /etc/supervisor/supervisord.conf

# 12. 暴露端口
EXPOSE 80 4422 5001

# 13. 健康检查
#HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
#    CMD curl -f http://localhost:80/ || exit 1

# 14. 使用 Supervisord 启动所有服务
#CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]

# 使用简单启动脚本
COPY start_container.sh /start_container.sh
RUN chmod +x /start_container.sh
CMD ["/start_container.sh"]
