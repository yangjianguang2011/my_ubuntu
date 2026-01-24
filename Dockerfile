# 使用更小的基础镜像
FROM ubuntu:22.04

# 1. 设置时区和镜像源（合并操作）
ENV TZ=Asia/Shanghai
 RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
     cp /etc/apt/sources.list /etc/apt/sources.list.bak && \
     echo "deb http://mirrors.ustc.edu.cn/ubuntu/ jammy main restricted universe multiverse" > /etc/apt/sources.list && \
     echo "deb http://mirrors.ustc.edu.cn/ubuntu/ jammy-updates main restricted universe multiverse" >> /etc/apt/sources.list && \
     echo "deb http://mirrors.ustc.edu.cn/ubuntu/ jammy-backports main restricted universe multiverse" >> /etc/apt/sources.list && \
     echo "deb http://mirrors.ustc.edu.cn/ubuntu/ jammy-security main restricted universe multiverse" >> /etc/apt/sources.list 
#RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
#    sed -i 's/archive.ubuntu.com/mirrors.ustc.edu.cn/g' /etc/apt/sources.list && \
#    sed -i 's/security.ubuntu.com/mirrors.ustc.edu.cn/g' /etc/apt/sources.list

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
    && rm -rf /var/lib/apt/lists/*

# 3. 提前配置pip使用国内源
#RUN pip3 config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
#    pip3 config set global.trusted-host mirrors.tuna.tsinghua.edu.cn && \
#    pip3 config set global.timeout 120



# 4. 提前安装PaddleOCR及其依赖（关键优化）
RUN pip3 install paddlepaddle==3.2.2 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
RUN pip3 install Pillow 
RUN pip3 install paddleocr
RUN mkdir -p /root/.paddlex && cd /root/.paddlex && python3 -c "import os;  from paddleocr import PaddleOCR; ocr=PaddleOCR(); print('Paddle OCR install OK');"

# 5. 安装Chrome相关（放到前面，这些变化少）
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    pip3 install webdriver-manager && \
    python3 -c "from webdriver_manager.chrome import ChromeDriverManager; import subprocess; subprocess.run(['cp', ChromeDriverManager().install(), '/usr/local/bin/chromedriver']); subprocess.run(['chmod', '+x', '/usr/local/bin/chromedriver'])"


#6. SSH Config
RUN mkdir -p /var/run/sshd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#Port 22/Port 4422/' /etc/ssh/sshd_config && \
    echo 'root:rootpassword' | chpasswd && \
    useradd -m -s /bin/bash ubuntu && \
    echo 'ubuntu:ubuntupass' | chpasswd && \
    usermod -aG sudo ubuntu && \
    # 允许root登录
    echo "PermitRootLogin yes" >> /etc/ssh/sshd_config


# 8. 安装项目依赖（分开处理，便于缓存）
# Stock Monitor
COPY ./stock_monitor/requirements.txt /tmp/stock_requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/stock_requirements.txt && rm /tmp/stock_requirements.txt

# NEWS
COPY ./news/requirements.txt /tmp/news_requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/news_requirements.txt && rm /tmp/news_requirements.txt



# 9. 复制代码文件（放在最后，这样代码变更不会影响前面的层）
# 复制Nginx配置
COPY default /etc/nginx/sites-enabled/default
COPY nginx.conf /etc/nginx/nginx.conf
# IPTV
COPY ./iptv /root/iptv
# NEWS
COPY ./news /root/news
# Stock Monitor
COPY ./stock_monitor /root/stock_monitor
# 创建目录结构
RUN mkdir -p /data/stock_monitor && mkdir -p /var/log/cron



# 10. 设置权限
RUN chmod +x \
    /root/iptv/download_m3u.py \
    /root/news/run.sh \
    /root/stock_monitor/run_eastmoney_analyst.sh \
    /root/stock_monitor/check_stock_monitor.sh

# 11. 配置Cron作业（使用单独文件便于管理）
RUN echo "0 1 * * * root cd /root/stock_monitor && /bin/bash /root/stock_monitor/check_stock_monitor.sh >> /var/log/cron.log 2>&1" >> /etc/crontab && \
    echo "0 23 * * * root cd /root/iptv && /usr/bin/python3 download_m3u.py >> /var/log/cron.log 2>&1" >> /etc/crontab && \
    echo "0 */8 * * * root cd /root/news/ && /bin/bash /root/news/run.sh >> /var/log/cron.log 2>&1" >> /etc/crontab && \
    echo "0 23 * * * root cd /root/stock_monitor && /bin/bash /root/stock_monitor/run_eastmoney_analyst.sh >> /var/log/cron.log 2>&1" >> /etc/crontab


# 14. 暴露端口
EXPOSE 80 4422 5001
RUN cd /root/stock_monitor && /bin/bash /root/stock_monitor/check_stock_monitor.sh 
CMD ["sh", "-c", "service ssh start && cron && /root/stock_monitor/check_stock_monitor.sh & nginx -g 'daemon off;'"]
