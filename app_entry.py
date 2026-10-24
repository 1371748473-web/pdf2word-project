"""PyInstaller 打包入口。

无参数启动图形界面；带参数时按命令行模式转换，例如：
    PDF转Word.exe input.pdf --mode scan --dpi 300
"""

import sys


def _run():
    if getattr(sys, "frozen", False) and len(sys.argv) > 1:
        # 命令行直通：便于脚本调用与打包环境自检
        from pdf2word.cli import main as cli_main

        cli_main()
    else:
        from pdf2word.gui import main as gui_main

        gui_main()


if __name__ == "__main__":
    _run()
