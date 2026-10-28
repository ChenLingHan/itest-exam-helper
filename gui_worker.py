"""GUI 后台进程。标准输出只发送 JSON 事件，配置通过管道传入。"""
import json
import logging
import sys
import os
from app_paths import RESOURCE_ROOT, DATA_ROOT, VERSION


def emit(event, **data):
    print(json.dumps({"event": event, **data}, ensure_ascii=False), flush=True)


class EventLog(logging.Handler):
    def emit(self, record):
        emit("log", message=self.format(record))


def refresh_papers(runner):
    """读取列表时保留答题页，供未交卷的用户检查答案。"""
    original=runner.driver.current_window_handle
    try:
        runner.driver.switch_to.window(runner.list_window)
        return runner.papers()
    finally:
        if original in runner.driver.window_handles:
            runner.driver.switch_to.window(original)


def main():
    from exam_runner import ExamRunner, ListeningSolver, ROOT, parse_groups

    logs = ROOT / ".exam_work"
    logs.mkdir(exist_ok=True)
    handler = EventLog()
    handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.FileHandler(logs / "latest.log", encoding="utf-8")])
    runner = None
    papers = []
    try:
        for line in sys.stdin:
            command = json.loads(line)
            try:
                if command["action"] == "load":
                    if runner and runner.driver:
                        runner.driver.quit()
                    runner = ExamRunner(command["config"])
                    runner.start()
                    runner.login()
                    papers = runner.papers()
                    emit("papers", papers=papers)
                elif command["action"] == "run":
                    if runner is None or runner.driver is None:
                        raise RuntimeError("请先登录并获取试卷。")
                    paper = papers[command["index"]]
                    runner.enter(paper, exam_code=command.get("exam_code", ""))
                    html = runner.driver.page_source
                    (runner.cache / "page.html").write_text(html, encoding="utf-8")
                    answers = ListeningSolver(runner.config, runner.cache).prepare(parse_groups(html))
                    runner.fill(answers)
                    if command["auto_submit"]:
                        refreshed=runner.submit(answers)
                        papers=refreshed if isinstance(refreshed,list) else refresh_papers(runner)
                        emit("done", submitted=True, papers=papers)
                    else:
                        try:
                            papers=refresh_papers(runner)
                            emit("done", submitted=False, papers=papers)
                        except Exception:
                            # 列表更新失败不能抹掉已经成功填写的事实。
                            emit("done", submitted=False, refresh_error=True)
                elif command["action"] == "close":
                    break
            except Exception as error:
                if runner and runner.driver and runner.cache:
                    try:
                        (runner.cache / "error-page.html").write_text(runner.driver.page_source, encoding="utf-8")
                        runner.driver.save_screenshot(str(runner.cache / "error-page.png"))
                    except Exception:
                        pass
                # 原始异常可能带请求信息，只在界面展示经过清理的摘要。
                message = str(error).split("Stacktrace:")[0]
                for secret in (runner.config.get("password"), runner.config.get("ai", {}).get("apikey")) if runner else ():
                    if secret:
                        message = message.replace(str(secret), "***")
                emit("error", message=message or type(error).__name__)
    finally:
        if runner and runner.driver:
            runner.driver.quit()


if __name__ == "__main__":
    try:
        os.chdir(RESOURCE_ROOT)
        DATA_ROOT.mkdir(parents=True, exist_ok=True)
        if '--self-test' in sys.argv:
            import openai, selenium, yaml, parsel, webview
            from vosk import Model, SetLogLevel
            from exam_runner import ListeningSolver
            SetLogLevel(-1)
            model = Model('model')
            import subprocess
            subprocess.run([str(RESOURCE_ROOT/'lib'/'ffmpeg.exe'), '-version'], check=True, capture_output=True)
            emit('self-test', version=VERSION, ok=True)
            raise SystemExit(0)
        main()
    except Exception as error:
        emit("error", message=f"后台启动失败：{type(error).__name__}。请重新安装最新版本。")
        raise SystemExit(1)
