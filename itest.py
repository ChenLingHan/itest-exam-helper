import json
import os
import shutil
import time
from urllib.parse import urlparse, parse_qs

from husky_spider_utils import SeleniumSession
from selenium.webdriver.common.by import By

from kimi_model import ItestKimi
from mp32str import mp3_to_wav, wav_to_str
from loguru import logger


class ExamEntryError(RuntimeError):
    """考试入口不可用或网站拒绝进入时，给出明确原因。"""


class ITest:
    base_url = "https://sso.unipus.cn/sso/login?service=https%3A%2F%2Fitestcloud.unipus.cn%2Futest%2Fitest%2Flogin%3F_rp%3D%252Fitest%253Fx%253D1742213323268"

    def __init__(self, username, password, api_key, model="deepseek-chat", base_url="https://api.deepseek.com/v1",
                 driver_type="edge"):
        self.session = SeleniumSession(self.base_url, driver_type=driver_type)
        self.ai_client = ItestKimi(api_key=api_key, model=model, base_url=base_url)
        self.login(username, password)

    def login(self, username, password):
        self.session.send_key("input[name='username']", username)
        self.session.send_key("input[name='password']", password)
        self.session.click(".help-block input[type='checkbox']")
        self.session.click("#login")

    def get_exams(self):
        self.session.selenium_get("https://itestcloud.unipus.cn/utest/itest/s/exam")
        exams_list = []

        def get_res(page: int):
            payload = {
                "curPage": page,
                "pageSize": 5
            }
            res = self.session.post("https://itestcloud.unipus.cn/utest/itest-mobile-api/student/exam/list",
                                    json=payload)
            if res.json()['msg'] == "SUCCESS":
                return res.json()['rs']['totalPage'], res.json()['rs']['data']
            else:
                return None

        total_page, data = get_res(1)
        exams_list.extend(data)
        if total_page > 1:
            for i in range(2, total_page + 1):
                _, data = get_res(page=i)
                exams_list.extend(data)
        return exams_list

    def get_mock(self):
        self.session.selenium_get("https://itestcloud.unipus.cn/utest/itest/s/train")
        res = self.session.get("https://itestcloud.unipus.cn/utest/itest/s/jcxl/mock")
        from parsel import Selector
        html = Selector(text=res.text)
        mock_table = html.css(".paper-table tbody tr")
        mock_data = []
        for tr in mock_table:
            tds = tr.css("td")
            mock_data.append({
                "id": tds[0].css("::text").extract_first(),
                "mock_id": tds[1].css("::text").extract_first(),
                "name": tds[2].css("::text").extract_first(),
                "times": tds[3].css("::text").extract_first(),
                "score": tds[4].css("::text").extract_first(),
            })
        return mock_data

    def to_mock_exam(self, mock_info):
        mock_id = mock_info['mock_id']
        url = f"https://itestcloud.unipus.cn/utest/itest/s/jcxl/mock/doMockTest?ppId={mock_id}&returnUrl=https://itestcloud.unipus.cn/utest/itest/s/jcxl/mock"
        self.session.selenium_get(url)
        current_url = self.session.get_current_url()
        parsed_url = urlparse(current_url)
        params = parse_qs(parsed_url.query)
        token = params.get('token', [None])[0]
        self.session.try_click(".layui-layer-btn0", max_attempt=1, timeout=5)
        self.common_to_exam(token=token, return_url='https://itestcloud.unipus.cn/utest/itest/s/jcxl/mock&skipEnvTest=true')

    @staticmethod
    def _entry_data(response, field, action, success_code=None):
        if not 200 <= response.status_code < 300:
            raise ExamEntryError(f"{action}失败：网站返回 HTTP {response.status_code}。")
        try:
            result = response.json()
        except ValueError as error:
            raise ExamEntryError(f"{action}失败：网站未返回有效的 JSON，请检查登录状态。") from error
        if not isinstance(result, dict):
            raise ExamEntryError(f"{action}失败：网站响应格式异常。")
        message = result.get("msg") or result.get("message") or "网站未提供原因"
        if success_code is not None and result.get("code") not in (success_code, str(success_code)):
            raise ExamEntryError(f"{action}失败：{message}（返回码：{result.get('code', '未提供')}）。")
        data = result.get(field)
        if not isinstance(data, dict):
            raise ExamEntryError(f"{action}失败：网站未返回 {field} 字段；提示：{message}。")
        return data

    def common_to_exam(self, token:str, return_url:str):
        if not token:
            raise ExamEntryError("无法进入考试：网站未提供考试令牌，请重新从试卷列表进入。")
        payload = {
            "token": token
        }
        data = {}
        self.session.headers.update(payload)
        res = self.session.post("https://itestcloud.unipus.cn/utest/itest-mobile-api/student/exam/examToken", data=data)
        entry = self._entry_data(res, "rs", "获取答题入口")
        if not isinstance(entry.get("url"), str) or not entry["url"]:
            raise ExamEntryError("无法进入考试：网站未返回有效的答题地址。")
        url = entry["url"] + f"&returnUrl={return_url}"
        self.session.selenium_get(url)
        self.session.try_click(".layui-layer-btn0", max_attempt=1, timeout=3)
        self.session.try_click("#success-ok", max_attempt=1, timeout=3)

    def to_exam(self, exam_info):
        if "type" not in exam_info:
            raise ExamEntryError("无法确定试卷类型，请重新启动程序并获取试卷列表。")
        ksd_id = exam_info['ksdId']
        payload = {
            "examId": ksd_id,
            "examCode": ""
        }
        if exam_info.get('examCodeFlag'):
            payload['examCode'] = input("请输入六位考试码:")
        # 与网站一致：type=0 使用班级考试入口，其余类型使用考试入口。
        entry_type = "clsanswer" if exam_info["type"] in (0, "0") else "exam"
        res = self.session.post(f"https://itestcloud.unipus.cn/utest/itest/s/{entry_type}/judgeEntry", data=payload)
        entry = self._entry_data(res, "data", "进入所选试卷", success_code=1)
        url = entry.get("url")
        token = entry.get("token")
        if not isinstance(url, str) or not url or not isinstance(token, str) or not token:
            raise ExamEntryError("无法进入考试：网站未返回有效的答题地址或考试令牌。")

        url = url + "&returnUrl=https://itestcloud.unipus.cn/utest/itest/s/exam"
        self.session.selenium_get(url)
        self.session.try_click(".layui-layer-btn0", max_attempt=1, timeout=5)
        self.common_to_exam(token, 'https://itestcloud.unipus.cn/utest/itest/s/exam&skipEnvTest=true')

    def download_mp3(self):
        sections = self.session.get_element_selector("#main-content .itest-section")
        all_hear = sections.css(".itest-hear-reslist::text").getall()
        hear_list = []
        if os.path.exists("hear_temp"):
            shutil.rmtree("hear_temp")
        os.mkdir("hear_temp")
        for item in all_hear:
            hear_list.extend(json.loads(item))
        for i, hear in enumerate(hear_list):  # type: int, str

            if hear.startswith("http"):
                res = self.session.get(hear, is_refresh=False)
                with open(f"./hear_temp/hear{i}.mp3", "wb") as f:
                    f.write(res.content)

    def mp3_to_str(self):
        mp3_to_wav()
        mp3_str = wav_to_str()
        return mp3_str

    def ai_get_ans(self):
        logger.info("下载听力资源中...")
        self.download_mp3()
        logger.info("转换听力资源中...")
        mp3_str = self.mp3_to_str()
        logger.success(f"听力文本: {mp3_str}")
        page_source = self.session.get_element_selector("#main-content .itest-section").getall()
        page_source_data = "".join(page_source)
        logger.info("ai生成答案中...")
        ans_data = self.ai_client.write(page_source_data, mp3_str)['ans']
        logger.info("ai生成完成！")
        return ans_data

    def write_ans(self, ans: list):
        logger.info("即将为您填写答案!")
        for i, ans_data in enumerate(ans):
            qid = ans_data['qid']
            q_type = ans_data['type']
            css = ans_data['css']
            a = ans_data['ans']
            logger.success(f"正在完成题目{qid}: {a}")
            if q_type == "write":
                self.session.send_key(css, a)
                if i != len(ans) - 1:
                    self.next_page()
            elif q_type == "select":
                self.session.try_click(css, max_attempt=1, timeout=5)
                if i != len(ans) - 1:
                    next_ans = ans[i + 1]
                    if next_ans['type'] != "write":
                        if next_ans['qsubindex'] == "1":
                            self.next_page()
                    else:
                        self.next_page()
            elif q_type == "input":
                self.session.send_key(css, a)
                if i != len(ans) - 1:
                    next_ans = ans[i + 1]
                    if next_ans['type'] != "write":
                        if next_ans['qsubindex'] == "1":
                            self.next_page()
                    else:
                        self.next_page()

    def submit(self, sleep_time=3):
        time.sleep(sleep_time)
        self.session.click("#submit-answer", timeout=10)
        self.session.click(".layui-layer-btn0", timeout=10)
        time.sleep(5)

    def next_page(self):
        self.session.try_click("#footer .goto a", max_attempt=1, timeout=3)


