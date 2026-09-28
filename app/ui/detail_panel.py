"""Rich text detail panel showing analysis interpretation."""

from PyQt5.QtWidgets import QTextBrowser

from app.analysis.metrics_calculator import MetricsResult, WindowMetrics
from app.config import TABLE_DECIMALS


class DetailPanel(QTextBrowser):
    """Read-only HTML panel with natural language analysis interpretation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenExternalLinks(False)
        self.setMinimumHeight(150)
        self.setMaximumHeight(250)
        self.setStyleSheet("""
            QTextBrowser {
                background-color: #fafafa;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
        """)

    def show_loading(self, message: str):
        self.setHtml(f"""
        <div style="color: #666; text-align: center; padding: 20px;">
            <p style="font-size: 14px;">⏳ {message}</p>
        </div>
        """)

    def show_error(self, error: str):
        self.setHtml(f"""
        <div style="color: #c62828; padding: 10px;">
            <p><b>错误</b></p>
            <p>{error}</p>
        </div>
        """)

    def show_results(self, result: MetricsResult):
        """Generate HTML from MetricsResult."""
        html = f"""
        <div style="font-family: 'Microsoft YaHei', sans-serif; color: #333;">
            <p><b>基金信息</b>：{result.fund_name} ({result.fund_code})</p>
        """

        if result.benchmark_name:
            html += f"""
            <p><b>业绩比较基准</b>：{result.benchmark_name}
            <span style="color: #888;">(代码: {result.benchmark_code})</span></p>
            """
            if result.raw_benchmark_str:
                html += f'<p style="color: #888; font-size: 12px;">基准说明: {result.raw_benchmark_str}</p>'
        else:
            html += """
            <p><b>业绩比较基准</b>：<span style="color: #c62828;">未检测到权益类基准</span></p>
            """

        # Add interpretation for each window
        html += '<hr style="border: none; border-top: 1px solid #eee;">'
        html += "<p><b>核心解读</b>：</p>"

        for label in ["3年", "1年", "6个月", "3个月", "1个月", "1周"]:
            if label not in result.window_results:
                continue
            wm = result.window_results[label]
            html += self._interpret_window(wm)

        html += """
        <hr style="border: none; border-top: 1px solid #eee;">
        <p style="color: #888; font-size: 11px;">
            <b>说明</b>：Jensen α 和择时 γ 的 p 值 < 0.05 表示统计显著。
            绿色 = 显著为正，黄色 = 不显著为正，橙色 = 不显著为负，红色 = 显著为负。
            夏普比率和信息比率已年化。
        </p>
        """

        html += "</div>"
        self.setHtml(html)

    def _interpret_window(self, wm: WindowMetrics) -> str:
        """Generate interpretation text for one time window."""
        parts = []
        label = wm.window_label
        parts.append(f'<p style="margin: 4px 0;"><b>📊 {label}</b>（{wm.n_observations} 个交易日）')

        if wm.error:
            parts.append(f'<span style="color: #999;"> — {wm.error}</span>')
            parts.append("</p>")
            return "".join(parts)

        # Jensen's Alpha
        if wm.jensen_alpha:
            alpha = wm.jensen_alpha.alpha
            p = wm.jensen_alpha.alpha_p_value
            sig = "显著" if wm.jensen_alpha.is_significant() else "不显著"
            direction = "正" if alpha > 0 else "负"
            parts.append(
                f'<br>Jensen α = {alpha:.{TABLE_DECIMALS}f} ({sig}{direction}, p={p:.4f})'
            )
            if wm.jensen_alpha.is_significant() and alpha > 0:
                parts.append('<span style="color: #2e7d32;"> ✅ 选股能力优秀</span>')
            elif wm.jensen_alpha.is_significant() and alpha < 0:
                parts.append('<span style="color: #c62828;"> ❌ 选股能力需警惕</span>')

        # Sharpe
        if wm.sharpe_ratio:
            sr = wm.sharpe_ratio.sharpe_ratio
            parts.append(f'<br>夏普比率 = {sr:.{TABLE_DECIMALS}f}')
            if sr > 1:
                parts.append('<span style="color: #2e7d32;"> ✅ 风险调整收益优秀</span>')
            elif sr > 0:
                parts.append('<span style="color: #f57f17;"> ⚠️ 风险调整收益一般</span>')
            else:
                parts.append('<span style="color: #c62828;"> ⚠️ 风险调整收益为负</span>')

        # Information Ratio
        if wm.information_ratio:
            ir = wm.information_ratio.information_ratio
            parts.append(f'<br>信息比率 = {ir:.{TABLE_DECIMALS}f}')
            if ir > 0.5:
                parts.append(' <span style="color: #2e7d32;">✅ 超额收益稳定</span>')
            elif ir > 0:
                parts.append(' <span style="color: #f57f17;">⚠️ 超额收益一般</span>')
            else:
                parts.append(' <span style="color: #c62828;">⚠️ 超额收益为负</span>')

        # H-M
        if wm.hm_model:
            g = wm.hm_model.beta_2
            gp = wm.hm_model.gamma_p_value
            parts.append(f'<br>H-M γ = {g:.{TABLE_DECIMALS}f} (p={gp:.4f})')
            if wm.hm_model.has_timing_ability():
                parts.append(' <span style="color: #2e7d32;">✅ 择时能力显著</span>')
            elif g > 0:
                parts.append(' <span style="color: #f57f17;">⚠️ 择时倾向为正但不显著</span>')
            else:
                parts.append(' <span style="color: #c62828;">⚠️ 择时倾向为负</span>')

        # T-M
        if wm.tm_model:
            g = wm.tm_model.beta_2
            gp = wm.tm_model.gamma_p_value
            parts.append(f'<br>T-M γ = {g:.{TABLE_DECIMALS}f} (p={gp:.4f})')
            if wm.tm_model.has_timing_ability():
                parts.append(' <span style="color: #2e7d32;">✅ 择时能力显著</span>')
            elif g > 0:
                parts.append(' <span style="color: #f57f17;">⚠️ 择时倾向为正但不显著</span>')
            else:
                parts.append(' <span style="color: #c62828;">⚠️ 择时倾向为负</span>')

        parts.append("</p>")
        return "".join(parts)
