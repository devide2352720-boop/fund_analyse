# 基金分析系统

一个基于 Python 和 PyQt5 的 Windows 桌面程序，用于搜索基金，并查看基金净值、区间表现、风险指标和市场择时分析。

## 功能

- 搜索基金并查看基金详情
- 获取基金净值与指数历史数据
- 计算区间收益、波动率等分析指标
- 展示市场择时与图表

## 环境要求

- Windows 10 或更高版本
- Python 3.10 或更高版本
- 可访问项目使用的数据来源

## 安装与启动

在项目目录打开 PowerShell：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

如果 PowerShell 阻止虚拟环境激活，也可以直接运行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

程序从公开数据服务获取基金和指数信息。网络接口、第三方依赖或数据源变化可能影响数据获取；首次启动可能需要等待数据加载。

## 项目结构

```text
基金分析/
├── app/
│   ├── analysis/   # 指标、选基和择时分析
│   ├── data/       # 数据获取、缓存和网络设置
│   ├── search/     # 基金搜索
│   └── ui/         # 桌面界面组件
├── main.py         # 程序入口
└── requirements.txt
```

运行后生成的 `cache/`、日志和 Python 缓存不需要提交到 GitHub。

## 说明

本项目用于学习和数据分析，不构成投资建议。历史数据和指标不代表未来表现，请自行核实数据并承担投资决策责任。

## License

目前尚未指定开源许可证。未经作者另行授权，GitHub 上公开代码仍受默认版权保护。
