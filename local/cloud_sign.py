# -*- coding: utf8 -*-
import os
import time
import asyncio
import re
import json
import requests
from lxml import etree
from bs4 import BeautifulSoup
requests.packages.urllib3.disable_warnings()
from config import *


class AutoSign(object):

    def __init__(self, username, password, schoolid=None):
        """初始化就进行登录"""
        self.headers = {
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.100 Safari/537.36'}
        self.session = requests.session()
        self.session.headers = self.headers
        self.username = username
        self.password = password
        self.schoolid = schoolid

    def set_cookies(self):
        """设置cookies"""
        if not self.check_cookies():
            # 无效则重新登录，并保存cookies
            login_status = self.login()
            if login_status == 1000:
                self.save_cookies()
            else:
                return 1001
        return 1000

    def save_cookies(self):
        """保存cookies"""
        new_cookies = self.session.cookies.get_dict()
        with open(COOKIES_FILE_PATH, "r") as f:
            data = json.load(f)
            data[self.username] = new_cookies
            with open(COOKIES_FILE_PATH, 'w') as f2:
                json.dump(data, f2)

    def check_cookies(self):
        """检测json文件内是否存有cookies,有则检测，无则登录"""
        if "cookies.json" not in os.listdir(COOKIES_PATH):
            with open(COOKIES_FILE_PATH, 'w+') as f:
                f.write("{}")

        with open(COOKIES_FILE_PATH, 'r') as f:
            # json文件有无账号cookies, 没有，则直接返回假
            try:
                data = json.load(f)
                cookies = data[self.username]
            except Exception:
                return False

            # 找到后设置cookies
            cookies_jar = requests.utils.cookiejar_from_dict(cookies)
            self.session.cookies = cookies_jar

            # 检测cookies是否有效
            r = self.session.get(
                'http://i.mooc.chaoxing.com/app/myapps.shtml',
                allow_redirects=False)
            if r.status_code != 200:
                print("cookies已失效")
                return False
            else:
                print("cookies有效哦")
                return True

    def login(self):
        # 登录-手机邮箱登录
        r = self.session.get(
            'https://passport2.chaoxing.com/api/login?name={}&pwd={}&schoolid={}&verify=0'.format(
                self.username,
                self.password,
                self.schoolid if self.schoolid else ""),
            headers=self.headers)
        if r.status_code == 403:
            return 1002
        data = json.loads(r.text)
        if data['result']:
            print("登录成功")
            return 1000  # 登录成功
        else:
            return 1001  # 登录信息有误

    def check_activeid(self, activeid):
        """检测activeid是否存在，不存在则添加"""
        activeid += self.username
        if "activeid.json" not in os.listdir(ACTIVEID_PATH):
            with open(ACTIVEID_FILE_PATH, 'w+') as f:
                f.write("{}")

        with open(ACTIVEID_FILE_PATH, 'r') as f:
            try:
                # 读取文件
                data = json.load(f)
                if data[activeid]:
                    return True
            except BaseException:
                # 如果出错，则表示没有此activeid，添加此activeid
                with open(ACTIVEID_FILE_PATH, 'w') as f2:
                    data[activeid] = True
                    json.dump(data, f2)
                return False

    def get_all_classid(self) -> list:
        """获取课程主页中所有课程的classid和courseid"""
        res = []
        r = self.session.get(
            'http://mooc1-2.chaoxing.com/visit/interaction',
            headers=self.headers)
        soup = BeautifulSoup(r.text, "lxml")
        courseId_list = soup.find_all('input', attrs={'name': 'courseId'})
        classId_list = soup.find_all('input', attrs={'name': 'classId'})
        classname_list = soup.find_all('h3', class_="clearfix")
        for i, v in enumerate(courseId_list):
            res.append((v['value'], classId_list[i]['value'],
                        classname_list[i].find_next('a').text))
        print(res)
        return res

    async def get_activeid(self, classid, courseid, classname):
        """访问任务面板获取课程的活动id"""
        # re_rule = r'<div class="Mct" onclick="activeDetail\((.*),2,null\)">[\s].*[\s].*[\s].*[\s].*<dd class="green">.*</dd>[\s]+[\s]</a>[\s]+</dl>[\s]+<div class="Mct_center wid660 fl">[\s]+<a href="javascript:;" shape="rect">(.*)</a>'
        re_rule = r'([\d]+),2'
        r = self.session.get(
            'https://mobilelearn.chaoxing.com/widget/pcpick/stu/index?courseId={}&jclassId={}'.format(
                courseid, classid), headers=self.headers, verify=False)
        # res = re.findall(re_rule, r.text)
        res = []
        h = etree.HTML(r.text)
        activeid_list = h.xpath('//*[@id="startList"]/div/div/@onclick')
        sign_type_list = h.xpath('//*[@id="startList"]/div/div/div/a/text()')
        for activeid, sign_type in zip(activeid_list, sign_type_list):
            activeid = re.findall(re_rule, activeid)
            if not activeid:
                continue
            res.append((activeid[0], sign_type))

        n = len(res)
        if n == 0:
            return None
        else:
            d = {'num': n, 'class': {}}
            for i in range(n):
                # 预防同一门课程多个签到任务的情况
                d['class'][i] = {
                    'classid': classid,
                    'courseid': courseid,
                    'activeid': res[i][0],
                    'classname': classname,
                    'sign_type': res[i][1]
                }
            return d

    def general_sign(self, classid, courseid, activeid):
        """普通签到"""
        r = self.session.get(
            'https://mobilelearn.chaoxing.com/widget/sign/pcStuSignController/preSign?activeId={}&classId={}&fid=39037&courseId={}'.format(
                activeid,
                classid,
                courseid),
            headers=self.headers,
            verify=False)
        title = re.findall('<title>(.*)</title>', r.text)[0]
        if "签到成功" not in title:
            # 网页标题不含签到成功，则为拍照签到
            return self.tphoto_sign(activeid)
        else:
            sign_date = re.findall('<em id="st">(.*)</em>', r.text)[0]
            s = {
                'date': sign_date,
                'status': title
            }
            return s

    def hand_sign(self, classid, courseid, activeid):
        """手势签到"""
        hand_sign_url = "https://mobilelearn.chaoxing.com/widget/sign/pcStuSignController/signIn?&courseId={}&classId={}&activeId={}".format(
            courseid, classid, activeid)
        r = self.session.get(hand_sign_url, headers=self.headers, verify=False)
        title = re.findall('<title>(.*)</title>', r.text)
        sign_date = re.findall('<em id="st">(.*)</em>', r.text)[0]
        s = {
            'date': sign_date,
            'status': title
        }
        return s

    def qcode_sign(self, activeId):
        """二维码签到"""
        params = {
            'name': '',
            'activeId': activeId,
            'uid': '',
            'clientip': '',
            'useragent': '',
            'latitude': '-1',
            'longitude': '-1',
            'fid': '',
            'appType': '15'
        }
        res = self.session.get(
            'https://mobilelearn.chaoxing.com/pptSign/stuSignajax',
            params=params)
        s = {
            'date': time.strftime("%m-%d %H:%M", time.localtime()),
            'status': res.text
        }
        return s

    def addr_sign(self, activeId):
        """位置签到"""
        params = {
            'name': '',
            'activeId': activeId,
            'address': '中国',
            'uid': '',
            'clientip': '0.0.0.0',
            'latitude': '-2',
            'longitude': '-1',
            'fid': '',
            'appType': '15',
            'ifTiJiao': '1'
        }
        res = self.session.get(
            'https://mobilelearn.chaoxing.com/pptSign/stuSignajax',
            params=params)
        s = {
            'date': time.strftime("%m-%d %H:%M", time.localtime()),
            'status': res.text
        }
        return s

    def tphoto_sign(self, activeId):
        """拍照签到"""
        params = {
            'name': '',
            'activeId': activeId,
            'address': '中国',
            'uid': '',
            'clientip': '0.0.0.0',
            'latitude': '-2',
            'longitude': '-1',
            'fid': '',
            'appType': '15',
            'ifTiJiao': '1',
            'objectId': '5712278eff455f9bcd76a85cd95c5de3'
        }
        res = self.session.get(
            'https://mobilelearn.chaoxing.com/pptSign/stuSignajax',
            params=params)
        s = {
            'date': time.strftime("%m-%d %H:%M", time.localtime()),
            'status': res.text
        }
        return s

    def sign_in_type_judgment(self, classid, courseid, activeid, sign_type):
        """签到类型的逻辑判断"""
        if self.check_activeid(activeid):
            return

        if "手势" in sign_type:
            # test:('拍照签到', 'success')
            return self.hand_sign(classid, courseid, activeid)

        elif "二维码" in sign_type:
            return self.qcode_sign(activeid)

        elif "位置" in sign_type:
            return self.addr_sign(activeid)

        else:
            # '[2020-03-20 14:42:35]-[签到成功]'
            r = self.general_sign(classid, courseid, activeid)
            return r

    def sign_tasks_run(self):
        """开始所有签到任务"""
        tasks = []
        res = []
        # 获取所有课程的classid和course_id
        classid_courseId = self.get_all_classid()

        # 使用协程获取所有课程activeid和签到类型
        for i in classid_courseId:
            coroutine = self.get_activeid(i[1], i[0], i[2])
            tasks.append(coroutine)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(asyncio.gather(*tasks))
        loop.close()
        for r in result:
            if r:
                for d in r['class'].values():
                    s = self.sign_in_type_judgment(
                        d['classid'],
                        d['courseid'],
                        d['activeid'],
                        d['sign_type'])
                    if s:
                        # 签到课程， 签到时间， 签到状态
                        sign_msg = {
                            'name': d['classname'],
                            'date': s['date'],
                            'status': s['status']
                        }
                        res.append(sign_msg)

        if res:
            final_msg = {
                'msg': 2001,
                'detail': res,
            }
        else:
            final_msg = {
                'msg': 2000,
                'detail': STATUS_CODE_DICT[2000]
            }
        return final_msg


def server_chan_send(msgs, sckey=None):
    """server酱将消息推送至微信"""
    desp = ''
    for msg in msgs:
        desp = '|  **课程名**  |   {}   |\r\r| :----------: | :---------- |\r\r'.format(
            msg['name'])
        desp += '| **签到时间** |   {}   |\r\r'.format(msg['date'])
        desp += '| **签到状态** |   {}   |\r\r'.format(msg['status'])

    params = {
        'text': '您的网课签到消息来啦！',
        'desp': desp
    }
    if sckey:
        requests.get(
            'https://sc.ftqq.com/{}.send'.format(sckey),
            params=params)
    else:
        requests.get(SERVER_CHAN['url'], params=params)


def run_local():
    """本地运行使用"""
    try:
        s = AutoSign(USER_INFO['username'], USER_INFO['password'])
        login_status = s.set_cookies()
        if login_status != 1000:
            return {
                'msg': login_status,
                'detail': '登录失败，' + STATUS_CODE_DICT[login_status]
            }

        result = s.sign_tasks_run()
        detail = result['detail']
        if result['msg'] == 2001:
            if SERVER_CHAN['status']:
                server_chan_send(detail)

        return detail
    except BaseException:
        return {'msg': 4000, 'detail': STATUS_CODE_DICT[4000]}


if __name__ == '__main__':
    try:
        print(run_local())
    except Exception as e:
        print(e)