'''提出データのモデルとバリデーション。'''
import datetime
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field

from core.config import DEPARTMENT_PLACEHOLDER, JST, shift_month_label

# 従業員コードに紛れ込みやすい区切り文字（空白・ハイフン類・長音・カンマ）
_CODE_NOISE = re.compile(r'[\s\-‐‑‒–—―−ーｰ,]')


def normalize_employee_code(value) -> str:
    '''従業員コードの表記ゆれをそろえる。

    全角→半角、空白やハイフン類の除去、スプレッドシート由来の「1234.0」、
    先頭ゼロ（「015366」→「15366」）を吸収する。数字以外を含むコードは
    半角化・大文字化だけして返す。
    '''
    if value is None:
        return ''
    code = unicodedata.normalize('NFKC', str(value))
    code = _CODE_NOISE.sub('', code)
    code = re.sub(r'\.0+$', '', code)
    if code.isdecimal():
        return str(int(code))
    return code.upper()


@dataclass(frozen=True)
class ShiftSubmission:
    '''1人分のシフト希望提出。'''
    employee_code: str
    name: str
    department: str
    target_hours: int
    day_requests: dict = field(default_factory=dict)
    remarks: str = ''

    def normalized(self) -> 'ShiftSubmission':
        '''従業員コードの表記ゆれをそろえ、前後の空白を落とした提出データを返す。'''
        return ShiftSubmission(
            employee_code=normalize_employee_code(self.employee_code),
            name=self.name.strip(),
            department=self.department,
            target_hours=self.target_hours,
            day_requests=dict(self.day_requests),
            remarks=self.remarks.strip(),
        )

    def validate(self) -> list:
        '''未入力項目のエラーメッセージ一覧を返す。空なら送信可。'''
        errors = []
        if not self.name.strip():
            errors.append('お名前が入力されていません。')
        if self.department == DEPARTMENT_PLACEHOLDER:
            errors.append('部門が選択されていません。')
        if not self.employee_code.strip():
            errors.append('従業員コードが入力されていません。')
        return errors

    def to_payload(self, target_year: int, target_month: int, submitted_at: datetime.datetime = None) -> dict:
        '''GAS へ送る JSON ペイロードを組み立てる。'''
        if submitted_at is None:
            submitted_at = datetime.datetime.now(JST)

        clean = self.normalized()
        payload = {
            '対象月': shift_month_label(target_year, target_month),
            '提出日時': submitted_at.strftime('%Y-%m-%d %H:%M:%S'),
            '従業員コード': clean.employee_code,
            '名前': clean.name,
            '部門': clean.department,
            '希望出勤時間': clean.target_hours,
        }
        payload.update(clean.day_requests)
        payload['備考'] = clean.remarks
        return payload

    def request_id(self, target_year: int, target_month: int) -> str:
        '''提出内容から決まる一意な ID。内容が同じなら何度計算しても同じ値になる。

        GAS 側の重複排除キーとして使う。連打・通信リトライ・リロード後の再提出の
        ように「まったく同じ内容」が複数回届いた場合は 2 件目以降が捨てられる。
        逆に内容を直して出し直せば別の ID になるので、修正版はきちんと保存される。

        提出日時は押した瞬間によって変わってしまうため、キーの計算から除く。
        '''
        payload = self.to_payload(target_year, target_month)
        payload.pop('提出日時', None)
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode('utf-8')).hexdigest()
