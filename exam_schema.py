"""Normalize supported iTEST form controls before any model call or browser write."""
import json
from parsel import Selector


class SchemaError(RuntimeError):
    pass


def text_content(node):
    return ' '.join(' '.join(node.xpath('.//text()[not(ancestor::script or ancestor::style or ancestor::*[contains(@class,"itest-hear-reslist")])] ').getall()).split())


def identity(attrs):
    return attrs.get('name') or attrs.get('id') or '|'.join(attrs.get(k, '') for k in ('qid', 'qindex', 'qsubindex'))


def parse_groups(html):
    page = Selector(text=html)
    all_controls = page.css('#main-content input[qid], #main-content textarea[qid], #main-content select[qid]')
    if not all_controls:
        raise SchemaError('页面没有加载出答题控件，不能开始生成答案。')
    groups, seen, covered = [], set(), 0
    for node in page.css('#main-content .itest-ques-set'):
        questions = {}
        controls = node.css('input[qid], textarea[qid], select[qid]')
        for control in controls:
            attrs = dict(control.attrib)
            tag = control.root.tag
            kind = attrs.get('type', 'text').lower() if tag == 'input' else tag
            if kind not in ('radio', 'checkbox', 'text', 'textarea', 'select') or 'multiple' in attrs or 'disabled' in attrs or 'readonly' in attrs:
                raise SchemaError(f'发现暂未适配的答题控件：{tag}/{kind}，已停止，未填写或交卷。')
            key = identity(attrs)
            if not key or not attrs.get('qid'):
                raise SchemaError('答题控件缺少唯一编号，已停止。')
            locator = {k: attrs[k] for k in ('qid', 'name', 'id', 'qindex', 'qsubindex', 'type') if k in attrs}
            if kind in ('radio', 'checkbox'):
                question = questions.setdefault(key, {'id': key, 'type': kind, 'index': attrs.get('qindex'), 'options': [], 'controls': []})
                if question['type'] != kind or 'value' not in attrs:
                    raise SchemaError('同一编号的控件类型冲突或选项缺少值。')
                question['options'].append({'value': attrs['value'], 'text': text_content(control.xpath('ancestor::label[1]'))})
                question['controls'].append({'tag': tag, 'attrs': {**locator, 'value': attrs['value']}})
            else:
                if key in questions:
                    raise SchemaError('多个填空控件使用相同编号，无法可靠定位，已停止。')
                question = {'id': key, 'type': kind, 'index': attrs.get('qindex'), 'controls': [{'tag': tag, 'attrs': locator}]}
                if kind == 'select':
                    question['options'] = [{'value': e.attrib.get('value', text_content(e)), 'text': text_content(e)} for e in control.css('option') if 'disabled' not in e.attrib and e.attrib.get('value', text_content(e))]
                if attrs.get('maxlength', '').isdigit():
                    question['max_length'] = int(attrs['maxlength'])
                questions[key] = question
        if not questions:
            raise SchemaError('发现无法识别答题控件的题组，已停止，未填写或交卷。')
        if seen.intersection(questions):
            raise SchemaError('检测到重复或嵌套题目编号，已停止。')
        for question in questions.values():
            if 'options' in question:
                values = [o['value'] for o in question['options']]
                if not values or len(set(values)) != len(values):
                    raise SchemaError('选项为空或值重复，已停止。')
        seen.update(questions)
        covered += len(controls)
        raw = node.css('.itest-hear-reslist::text').get()
        try:
            resources = json.loads(raw) if raw else []
        except ValueError as error:
            raise SchemaError('听力资源格式无效。') from error
        if not isinstance(resources, list):
            raise SchemaError('听力资源列表格式无效。')
        audio = list(dict.fromkeys(url for url in resources if isinstance(url, str) and url.startswith('https://') and '/quesres/' in url))
        section = node.xpath('ancestor::*[contains(concat(" ", normalize-space(@class), " "), " itest-section ")][1]')
        context = text_content(section if section else node)
        if (raw and any(resources)) and not audio:
            raise SchemaError('题目有听力资源但无法读取，已停止。')
        if (section if section else node).css('img, video, canvas, iframe, [contenteditable=true]'):
            raise SchemaError('题目含图片、视频或富文本控件，当前版本需要人工处理，已停止。')
        groups.append({'number': len(groups) + 1, 'audio': audio, 'context': context, 'questions': list(questions.values())})
    if not groups or covered != len(all_controls):
        raise SchemaError('未能完整读取所有题目，已停止。')
    return groups


def validate_answers(group, answers):
    if not isinstance(answers, list):
        raise SchemaError('模型没有返回答案列表。')
    expected = {q['id']: q for q in group['questions']}
    found = {}
    for answer in answers:
        if not isinstance(answer, dict) or not isinstance(answer.get('id'), str):
            raise SchemaError('模型返回了无效的题目编号。')
        key, value = answer['id'], answer.get('value')
        if key not in expected or key in found:
            raise SchemaError('模型返回了未知或重复的题目编号。')
        question = expected[key]
        kind = question.get('type', 'radio')
        options = {o['value'] for o in question.get('options', [])}
        if kind == 'checkbox':
            if not isinstance(value, list) or not value or any(not isinstance(v, str) or v not in options for v in value) or len(set(value)) != len(value):
                raise SchemaError('多选答案必须是非空且不重复的有效选项列表。')
            value = [o['value'] for o in question['options'] if o['value'] in value]
        elif not isinstance(value, str) or not value.strip():
            raise SchemaError('答案必须是非空字符串。')
        elif kind in ('radio', 'select') and value not in options:
            raise SchemaError('答案不在题目选项中。')
        elif kind in ('text', 'textarea') and len(value) > question.get('max_length', 50000):
            raise SchemaError('文字答案超出控件长度限制。')
        found[key] = value
    if set(found) != set(expected):
        raise SchemaError('模型遗漏了部分题目，已停止。')
    return [{'id': q['id'], 'value': found[q['id']]} for q in group['questions']]


# Locators come only from the parsed page. Model output never becomes code or CSS.
CONTROL_SCRIPT = r"""
const [questions, answers, write] = arguments;
const root = document.querySelector('#main-content');
const located = questions.map(q => q.controls.map(c => {
    const matches = [...root.querySelectorAll('input[qid],textarea[qid],select[qid]')]
        .filter(e => e.tagName.toLowerCase() === c.tag && Object.entries(c.attrs).every(([k,v]) => e.getAttribute(k) === v));
    if(matches.length !== 1 || matches[0].disabled || matches[0].readOnly) throw Error('Answer control changed');
    return matches[0];
}));
if(write) questions.forEach((q,i) => {
    const value = answers[i].value;
    located[i].forEach(e => {
        if(q.type === 'radio' || q.type === 'checkbox') {
            const desired = q.type === 'checkbox' ? value.includes(e.value) : value === e.value;
            if(e.checked !== desired) e.click();
        } else {
            const proto = q.type === 'textarea' ? HTMLTextAreaElement.prototype : q.type === 'select' ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
            Object.getOwnPropertyDescriptor(proto,'value').set.call(e,value);
            e.dispatchEvent(new Event('input',{bubbles:true}));
            e.dispatchEvent(new Event('change',{bubbles:true}));
            e.dispatchEvent(new Event('blur',{bubbles:true}));
        }
    });
});
return questions.map((q,i) => ({id:q.id, value:q.type === 'checkbox' ? located[i].filter(e=>e.checked).map(e=>e.value) : q.type === 'radio' ? located[i].find(e=>e.checked)?.value : located[i][0].value}));
"""
