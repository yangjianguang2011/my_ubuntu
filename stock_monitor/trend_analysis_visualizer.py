#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
趋势分析可视化工具
创建交互式 K 线图，显示均线、买卖点和密集成交区
"""

from logger_config import logger

# 检查 plotly 依赖
PLOTLY_AVAILABLE = False
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError as e:
    logger.error(f"plotly 模块未安装：{e}")
    logger.error("请运行：pip install plotly")
    PLOTLY_AVAILABLE = False


def create_trend_chart(stock_code, stock_name, df, signals, consolidation_zone=None, health_scores=None):
    """
    创建交互式趋势分析图表

    :param stock_code: 股票代码
    :param stock_name: 股票名称
    :param df: DataFrame，包含 OHLC 和均线数据
    :param signals: 买卖信号列表
    :param consolidation_zone: 密集成交区 {start_date, end_date, upper, lower}
    :param health_scores: 健康度分数列表（与 df 等长）
    :return: Plotly Figure 对象
    """
    # 检查 plotly 可用性
    if not PLOTLY_AVAILABLE:
        raise ImportError("plotly 模块不可用，请先安装：pip install plotly")

    logger.info(f"开始创建趋势图表：{stock_code} {stock_name}")

    # 参数校验
    if df is None or len(df) == 0:
        logger.error("DataFrame 为空")
        raise ValueError("DataFrame 不能为空")

    required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        logger.error(f"DataFrame 缺少必要列：{missing_columns}")
        raise ValueError(f"DataFrame 缺少必要列：{missing_columns}")

    logger.info(f"图表数据点数：{len(df)}, 日期范围：{df['date'].min()} ~ {df['date'].max()}")

    try:
        # 创建子图：主图 (60%) + 成交量 (20%) + 健康度 (20%)
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.60, 0.20, 0.20],
            subplot_titles=('K 线与均线', '成交量', '趋势健康度')
        )

        # ========== 主图：K 线 + 均线 ==========

        # K 线图（涨=红，跌=绿）
        fig.add_trace(
            go.Candlestick(
                x=df['date'],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='K 线',
                increasing_line_color='#EF5350',
                decreasing_line_color='#26A69A',
            ),
            row=1, col=1
        )

        # 均线
        fig.add_trace(go.Scatter(x=df['date'], y=df['ma5'],
                                line=dict(color='#FF9800', width=1), name='MA5'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['date'], y=df['ma20'],
                                line=dict(color='#2196F3', width=2), name='MA20'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['date'], y=df['ma60'],
                                line=dict(color='#9C27B0', width=2), name='MA60'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['date'], y=df['ma120'],
                                line=dict(color='#607D8B', width=2), name='MA120'), row=1, col=1)

        # 密集成交区高亮
        if consolidation_zone:
            fig.add_vrect(
                x0=consolidation_zone.get('start_date'),
                x1=consolidation_zone.get('end_date'),
                fillcolor="rgba(255, 235, 59, 0.3)",
                line_width=0,
                annotation_text="密集成交区",
                annotation_position="top",
                row=1, col=1
            )

        # 买卖点标记
        buy_signals = [s for s in signals if s.get('type') == 'BUY']
        sell_signals = [s for s in signals if s.get('type') == 'SELL']
        logger.info(f"买卖信号：买入 {len(buy_signals)} 个，卖出 {len(sell_signals)} 个")

        # 买入标记（绿色向上箭头）
        if buy_signals:
            fig.add_trace(go.Scatter(
                x=[s.get('date') for s in buy_signals],
                y=[s.get('price', 0) * 0.97 for s in buy_signals],
                mode='markers+text',
                marker=dict(symbol='arrow-up', color='#4CAF50', size=14),
                text=["买" for s in buy_signals],
                textposition="bottom center",
                name='买入',
                hovertext=[f"{s.get('signal', '')}" for s in buy_signals],
            ), row=1, col=1)

        # 卖出标记（红色向下箭头）
        if sell_signals:
            fig.add_trace(go.Scatter(
                x=[s.get('date') for s in sell_signals],
                y=[s.get('price', 0) * 1.03 for s in sell_signals],
                mode='markers+text',
                marker=dict(symbol='arrow-down', color='#F44336', size=14),
                text=["卖" for s in sell_signals],
                textposition="top center",
                name='卖出',
                hovertext=[f"{s.get('signal', '')}" for s in sell_signals],
            ), row=1, col=1)

        # ========== 第二行：成交量 ==========
        colors = ['#EF5350' if df['close'].iloc[i] >= df['open'].iloc[i] else '#26A69A'
                  for i in range(len(df))]
        fig.add_trace(go.Bar(
            x=df['date'],
            y=df['volume'],
            marker_color=colors,
            name='成交量',
            opacity=0.7
        ), row=2, col=1)

        # ========== 第三行：健康度 ==========
        if health_scores and len(health_scores) == len(df):
            fig.add_trace(go.Scatter(
                x=df['date'],
                y=health_scores,
                line=dict(color='#FF5722', width=2),
                name='健康度',
                fill='tozeroy'
            ), row=3, col=1)

            # 阈值线
            fig.add_hline(y=70, line_dash="dash", line_color="green", row=3, col=1)
            fig.add_hline(y=40, line_dash="dash", line_color="red", row=3, col=1)

        # ========== 布局配置 ==========
        fig.update_layout(
            height=800,
            showlegend=True,
            legend=dict(x=0.02, y=0.98, bgcolor='rgba(0,0,0,0.5)'),
            hovermode='x unified',
            xaxis_rangeslider_visible=False,
            template='plotly_white',
            title=dict(
                text=f'📊 {stock_name} ({stock_code}) - 趋势分析',
                font=dict(size=18)
            ),
            margin=dict(l=50, r=50, t=80, b=50)
        )

        # X 轴范围滑块
        fig.update_xaxes(
            rangeslider_visible=True,
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1 月", step="month", stepmode="backward"),
                    dict(count=3, label="3 月", step="month", stepmode="backward"),
                    dict(count=6, label="6 月", step="month", stepmode="backward"),
                    dict(count=1, label="1 年", step="year", stepmode="backward"),
                    dict(step="all")
                ])
            ),
            row=1, col=1
        )

        logger.info(f"趋势图表创建成功：{stock_code} {stock_name}")
        return fig

    except Exception as e:
        logger.error(f"创建趋势图表失败：{e}")
        raise


def chart_to_html(fig):
    """
    将图表转换为 JSON 字符串（用于前端 Plotly.newPlot 渲染）
    使用 HTML 模板中已加载的 plotly.js，避免重复加载
    """
    logger.info("开始将图表转换为 JSON 配置")

    # 参数校验
    if fig is None:
        logger.error("Figure 对象为 None")
        raise ValueError("Figure 对象不能为 None")

    try:
        # 返回 JSON 配置，让前端用 Plotly.newPlot 渲染
        chart_json = fig.to_json()
        logger.info(f"JSON 转换成功，长度：{len(chart_json)} 字符")
        return chart_json
    except Exception as e:
        logger.error(f"JSON 转换失败：{e}")
        raise
