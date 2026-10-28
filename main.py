from pathlib import Path

import yaml
from loguru import logger

from itest import ExamEntryError, ITest

def choose_number(prompt, total):
    while True:
        try:
            number = int(input(prompt).strip())
        except ValueError:
            print("请输入列表中的数字编号，输入 0 退出。")
            continue
        if 0 <= number <= total:
            return number
        print(f"请输入 0 到 {total} 之间的编号。")


def paper_name(paper):
    for key in ("examName", "paperName", "ksName", "name", "title"):
        if paper.get(key):
            return str(paper[key]).strip()
    return "未提供试卷名称"


def main():
    print("请选择试卷来源：\n1. 我的考试（教师发布的考试）\n2. 模拟训练\n0. 退出")
    mode = choose_number("请输入来源编号：", 2)
    if mode == 0:
        return 0

    with Path(__file__).with_name("config.yml").open(encoding="utf-8") as file:
        config = yaml.safe_load(file)

    itest = ITest(config['username'], config['password'], model=config['ai']['model'],
                  driver_type=config['driver_type'], api_key=config['ai']['apikey'], base_url=config['ai']['base_url'])
    papers = itest.get_exams() if mode == 1 else itest.get_mock()
    if not papers:
        logger.warning("当前来源没有可选择的试卷，请确认来源和账号。")
        return 0

    source_name = "我的考试" if mode == 1 else "模拟训练"
    print(f"\n{source_name}试卷列表：")
    for number, paper in enumerate(papers, start=1):
        paper_id = paper.get("ksdId") if mode == 1 else paper.get("mock_id")
        if paper_id is None:
            paper_id = paper.get("id", "未提供")
        print(f"{number}. {paper_name(paper)}（试卷编号：{paper_id}）")

    number = choose_number("请输入要做的试卷序号（0 退出）：", len(papers))
    if number == 0:
        return 0
    selected = papers[number - 1]
    print(f"\n已选择：{source_name} / {paper_name(selected)}")
    print("程序只处理这张试卷，答题完成后会自动交卷。")
    if input("确认开始？输入 y 继续，其他输入取消：").strip().lower() != "y":
        logger.info("已取消，未进入试卷。")
        return 0

    if mode == 1:
        itest.to_exam(selected)
    else:
        itest.to_mock_exam(selected)
    answers = itest.ai_get_ans()
    if not answers:
        logger.error("未生成答案，已停止自动交卷，请检查网页和模型返回结果。")
        return 1
    itest.write_ans(answers)
    logger.info("答案已填写，准备交卷...")
    itest.submit(sleep_time=config.get('sleep_time', 10))
    logger.info("已执行交卷操作，请以网页上的提交结果为准。")
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        logger.info("操作已取消。")
    except ExamEntryError as error:
        logger.error(str(error))
        raise SystemExit(1)
