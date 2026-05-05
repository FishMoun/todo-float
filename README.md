# 待办助手 — Windows 桌面悬浮任务窗

白色淡蓝风格、Always-on-top 悬浮窗，直连任务服务器，随时查看 / 添加 / 完成任务。

## 快速开始

```cmd
pip install -r requirements.txt
python vikunja_float.pyw
```

## 功能

- **查看** — 按优先级分组：P0 红 / P1 橙 / P2 蓝 / P3 灰
- **完成** — 点击复选框，即时切换
- **添加** — 底栏输入 + 选优先级，回车或点 `＋`
- **删除** — 点击任务右侧 `×`
- **刷新** — `🔄` 按钮（默认 60 秒自动）
- **设置** — `⚙` 调刷新间隔、置顶、重新登录
- **托盘** — 点 `✕` 最小化到系统托盘

## 登录

首次启动输入服务器地址与账号密码，token 有效期 30 天，过期自动弹出重登。

## 配置

编辑 `config.json`（仓库不含此文件）：

```json
{
  "base_url": "http://<IP>:3456",
  "username": "",
  "token": "",
  "project_id": 1,
  "always_on_top": true,
  "refresh_interval": 60,
  "window_geometry": "360x520+100+100"
}
```
