# NAS 部署说明

本项目以 **Docker 容器**方式跑在一台 fnOS NAS 上。本文只讲**怎么部署/更新/运维**；
网络问题的排查过程见 `docs/dev/NAS容器网络问题排查记录.md`。

---

## 1. 环境概览

| 项 | 值 |
|---|---|
| 宿主机 | fnOS（Debian 12），`192.168.50.50`，网卡 `eno1-ovs`（Open vSwitch） |
| 项目目录（构建上下文） | `/vol1/1000/docker/my-ubuntu/` |
| 容器名 | `ubuntu_openclaw` |
| 网络 | 自定义 bridge `my-ubuntu_my_network`（容器 IP `172.27.0.2`，网关 `172.27.0.1`） |
| 启动方式 | `docker compose up -d`（`privileged: true`，`restart: unless-stopped`） |

**端口映射**（`docker-compose.yml`）：

| 宿主 | 容器 | 用途 |
|---|---|---|
| `4400` | `80` | Nginx |
| `4401` | `5001` | **Stock Monitor Web 界面** |
| `4422` | `4422` | SSH |
| `38789` | `38789` | 预留 |

**数据卷**：

| 宿主 | 容器 | 说明 |
|---|---|---|
| `/vol1/1000/docker/my-ubuntu/run` | `/data` | **数据卷**（各模块 data_dir、日志、`cache.db` 都在这里，持久化） |
| `/vol1/1000/docker/my-ubuntu/apps/stockdb` | `/root/apps/stockdb` | stockdb SDK（`pybao` 内含 `stockdb.pyd`，非 pip 包） |
| `/vol1/1009/paddle_mount` | `/paddle` | PaddleOCR 模型 |
| `/vol1/1000/docker/openclaw` | `/root/.openclaw` | OpenClaw 工作空间 |

> ⚠️ **`/root/apps`（代码）在镜像内**，不是挂载。`/vol1/1000/docker/my-ubuntu/apps/` 只是
> **构建上下文**（`Dockerfile` 用 `COPY ./apps/xxx → /root/apps/xxx`）。
> 所以改了代码要么**重建镜像**，要么按 §3 用 `docker cp` 热更新。

**环境变量**（`docker-compose.yml`）：

- `TZ=Asia/Shanghai`、`LOG_LEVEL=INFO`
- `ENABLE_OPENCLAW=0`、`ENABLE_TELEGRAM=0`（可选功能开关，默认关闭，代码保留）
- `STOCK_MONITOR_STOCKDB_HOST=host.docker.internal`（**必须**，原因见 §5）
- `PYTHONPATH=/root/apps/eastmoney:/root/apps`

---

## 2. 首次部署 / 重建镜像

在 NAS 的项目目录下：

```bash
cd /vol1/1000/docker/my-ubuntu
sudo docker compose build
sudo docker compose up -d
```

> 打开可选功能需重建：`ENABLE_OPENCLAW=1 sudo docker compose build && sudo docker compose up -d`

容器启动脚本 `start_container.sh` 会：

1. 建好 `/var/run/sshd`、`/var/log/nginx`、`/data/logs/cron`、`/data/news`、
   `/data/iptv`、`/data/xueqiu_data`、`/data/analyst_data`、
   `/data/stock_monitor_data/database` 等目录；
2. 拉起 `sshd`、`nginx`、`cron`；
3. 拉起 `stock_monitor`（`cd /root/apps/stock_monitor && python3 start_app.py`），
   **带自动重启循环**（进程退出 5 秒后重拉）；
4. 可选拉起 OpenClaw（仅 `ENABLE_OPENCLAW=1` 且已安装时）。

---

## 3. 更新代码（不重建镜像）

代码在镜像里，改完要**传进容器**。标准流程：

```bash
# 1) 把改动文件放到 NAS 的构建上下文（宿主侧）
#    scp / rsync 到 /vol1/1000/docker/my-ubuntu/apps/stock_monitor/...

# 2) 从宿主上下文拷进容器
sudo docker cp /vol1/1000/docker/my-ubuntu/apps/stock_monitor/analyzers/conditions.py \
             ubuntu_openclaw:/root/apps/stock_monitor/analyzers/conditions.py

# 3) 重启容器（Python 代码需要重启才生效）
sudo docker restart ubuntu_openclaw

# 4) 校验容器内文件与本地一致（md5）
sudo docker exec ubuntu_openclaw md5sum /root/apps/stock_monitor/analyzers/conditions.py
```

> 前端静态资源（`web_static/`）与模板（`web_templates/`）同样用 `docker cp`；
> 静态资源改完可以不清缓存，但**浏览器要强刷**（`Ctrl+F5`）。

### ⚠️ 私有值：不要写进仓库或镜像，改用**挂载注入**

私有值（推送凭据、私有域名）**只住在 NAS 宿主目录**，git 与镜像里都只有脱敏版：

| 私有文件（不入库、不进镜像） | 宿主真实位置 | 仓库里的脱敏模板 |
|---|---|---|
| `config.ini` | `/vol1/1000/docker/my-ubuntu/apps/config.ini` | `apps/config.ini.example` |
| `web_templates/index.html` | `…/apps/stock_monitor/web_templates/index.html` | `…/index.html.example` |

`docker-compose.yml` 的 `volumes` 已把这两个宿主真文件**挂载覆盖**容器内的脱敏版：

```yaml
- /vol1/1000/docker/my-ubuntu/apps/config.ini:/root/apps/config.ini
- /vol1/1000/docker/my-ubuntu/apps/stock_monitor/web_templates/index.html:/root/apps/stock_monitor/web_templates/index.html
```

因此：

- **同步代码时不要再传这两个文件**（它们由挂载提供，传了也会被挂载盖住）；
  同步清单里其余文件（含 `core/notification.py`，它已不再含私有值）照常传。
- **重建容器/镜像不需要手动改回**：`sudo docker compose build && sudo docker compose up -d` 即可，
  镜像里是脱敏兜底版，运行时由挂载覆盖成真值。
- 想改私有值：**只改宿主那个文件**，然后 `sudo docker restart ubuntu_openclaw`（无需重建）。
- 改了真 `index.html` 后，请**同步更新 `index.html.example`**（私有域名 → `*.example.com`），
  否则镜像里的兜底版会陈旧。

---

## 4. 容器内定时任务

源文件 `configs/cron.d/myjobs`，`Dockerfile` COPY 到 `/etc/cron.d/myjobs`：

```
0 */8 * * *  root  cd /root/apps/news       && /bin/bash run.sh          >> /data/logs/cron/news.log 2>&1
0 23 * * *   root  cd /root/apps/iptv       && /usr/bin/python3 download_m3u.py >> /data/logs/cron/iptv.log 2>&1
10 23 * * *  root  cd /root/apps/xueqiu_api && /bin/bash run_xueqiu.sh   >> /data/logs/cron/xueqiu.log 2>&1
20 23 * * *  root  cd /root/apps/eastmoney  && /bin/bash run_eastmoney.sh >> /data/logs/cron/eastmoney.log 2>&1
```

> `/etc/cron.d/` 下的文件必须 **LF 换行**、以换行结尾，且第 6 列是用户名（`root`）。

---

## 5. 网络与防火墙（必读）

### 5.1 stockdb 必须用 `host.docker.internal`

stockdb 跑在**宿主机**上（`0.0.0.0:7899`）。容器**不能**用宿主 LAN IP
`192.168.50.50` 连它：

- fnOS 有一条策略路由 `from 192.168.50.50 lookup 10`，表 10 的默认路由走 LAN 网关，
  没有到 docker 网段的明细路由；
- stockdb 回包时源地址是 `192.168.50.50` → 命中该规则 → 回包被丢到 LAN 网关
  → 容器永远收不到 SYN-ACK → **连接超时**。

所以 `docker-compose.yml` 里：

```yaml
    extra_hosts:
      - "host.docker.internal:host-gateway"          # -> 172.17.0.1
    environment:
      - STOCK_MONITOR_STOCKDB_HOST=host.docker.internal
```

容器连 `172.17.0.1:7899`，回包源是网关 IP，不命中策略规则，正常走网桥。

### 5.2 UFW 必须放行 docker 网段

容器访问"宿主机自己"走 **INPUT 链**（访问外网走 FORWARD + NAT，通道不同）。
UFW 默认**不放行 docker 网段到宿主机**，且手工 `iptables` 规则重启即失效，所以要用
`ufw allow` 持久化（写入 `/etc/ufw/user.rules`，开机自动加载）：

```bash
sudo ufw allow from 172.16.0.0/12          # 覆盖 172.16~172.31，所有 docker 网桥
sudo ufw status numbered | grep 172        # 确认
```

只想放行单个端口：

```bash
sudo ufw allow from 172.16.0.0/12 to any port 7899 proto tcp
```

### 5.3 连通性自检

```bash
sudo docker exec ubuntu_openclaw python3 -c "import socket;s=socket.socket();s.settimeout(3);print(s.connect_ex(('host.docker.internal',7899)))"
# 0 = 通
```

---

## 6. stockdb 数据同步

**脚本**：NAS 上 `/vol1/1000/docker/my-ubuntu/apps/stockdb/sync_and_restart.sh`
（项目内留档：`configs/stockdb/sync_and_restart.sh`）

流程：**停库 → `sync_data` → 起库**，日志追加到 `./sync_cron.log`。

**crontab（NAS 普通用户，非 root；具体用户名见部署环境）**：

```
0 16 * * * /vol1/1000/docker/my-ubuntu/apps/stockdb/sync_and_restart.sh
@reboot sleep 30; cd /vol1/1000/docker/my-ubuntu/apps/stockdb && ./stockdb -d -s start ./stockdb.conf >> /vol1/1000/docker/my-ubuntu/apps/stockdb/sync_cron.log 2>&1
```

- 每天 16:00 同步 + 重启；开机后延迟 30s 自动拉起；
- stockdb 以 **NAS 普通用户（非 root）** 运行即可（只需目录读写权限 + 7899 端口 >1024），
  避免 root 与普通用户混用导致属主/pid 混乱。

---

## 7. 常用运维命令

```bash
# 容器状态 / 日志
sudo docker ps --format '{{.Names}}|{{.Status}}'
sudo docker logs -f --tail 100 ubuntu_openclaw

# 应用进程
sudo docker exec ubuntu_openclaw ps -ef | grep start_app.py

# 首页探活
sudo docker exec ubuntu_openclaw curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5001/

# 宿主 stockdb
sudo ss -tlnp | grep 7899
ps -ef | grep -i stockdb | grep -v grep
```

---

## 8. 其它约定

- **Python 环境**：容器内用系统 `python3`；本机（Windows）开发统一用
  `E:\work\code\.venv\Scripts\python.exe`。
- **数据清理**：`/data` 是持久卷，注意清理各模块的历史产物
  （`analyst_data/processed_*`、`xueqiu_data/<日期>` 等）。
- `configs/supervisord.conf` **实际未被使用**（`start_container.sh` 直接拉起各进程），属死配置。
