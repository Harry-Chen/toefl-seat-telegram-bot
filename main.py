#!/usr/bin/env python3

from fateadm_api import FateadmApi

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select

import traceback
import requests
import sys
import time
import json
from datetime import datetime, timedelta
from bot import Bot


USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.122 Safari/537.36'

options = Options()
options.add_argument('--headless')
options.add_argument(f'--user-agent="{USER_AGENT}"')

driver = webdriver.Firefox(options=options)
wait = WebDriverWait(driver, 5, 0.5)

config = json.load(open('config.json'))
fateadm_api = FateadmApi(app_id=None, app_key=None, pd_id=config['fateadm_id'], pd_key=config['fateadm_key'])
bot = Bot(config['telegram_token'])


def recognize_captcha(image_url):
    res = requests.get(image_url, headers={"User-Agent": USER_AGENT})
    captcha_result = fateadm_api.Predict("20400", res.content)
    if captcha_result.ret_code == 0:
        result = captcha_result.pred_rsp.value
        request_id = captcha_result.request_id
        return request_id, result
    else:
        raise Exception(f'Captcha API request failed: {captcha_result.ret_code} {captcha_result.err_msg}')


def fill_credentials():
    print('Filling credentials...')
    input_name = wait.until(EC.presence_of_element_located((By.ID, 'userName')))
    input_name.clear()
    input_name.send_keys(config['neea_username'])
    input_password = wait.until(EC.presence_of_element_located((By.ID, 'textPassword')))
    input_password.clear()
    input_password.send_keys(config['neea_password'])


def get_captcha():
    print('Getting captcha...')
    input_captcha = wait.until(EC.presence_of_element_located((By.ID, 'verifyCode')))
    input_captcha.click()
    captcha_img = wait.until((EC.presence_of_element_located((By.ID, "chkImg"))))
    retry_count = 0
    time.sleep(5)
    captcha_url = "loading"
    while captcha_url is None or 'loading' in captcha_url:
        captcha_url = driver.find_element_by_id('chkImg').get_attribute("src")
        retry_count += 1
        if retry_count == 10:
            raise Exception('Fetching captcha timeout')
        time.sleep(1)
    return captcha_url


def fill_captcha_and_login(captcha):
    print(f'Trying to login with captcha {captcha}...')
    input_captcha = wait.until(EC.presence_of_element_located((By.ID, 'verifyCode')))
    input_captcha.clear()
    input_captcha.send_keys(captcha)
    submit_button = wait.until(EC.presence_of_element_located((By.ID, 'btnLogin')))
    submit_button.click()
    try:
        wait.until(EC.text_to_be_present_in_element((By.XPATH, '//div[@class="myhome_info_cn"]/span[2]'), '21073302'))
        print('Login succeeded')
        return True
    except:
        print('Login failed')
        traceback.print_exc()
        return False


def crawl_toefl_info():
    driver.delete_all_cookies()
    driver.get('https://toefl.neea.cn/login')

    retry_count = 0
    req_id = None
    captcha = None

    while captcha is None or not fill_captcha_and_login(captcha):
        # ask for refund for previous results
        if req_id is not None:
            fateadm_api.Justice(req_id)
        fill_credentials()
        captcha_url = get_captcha()
        print(f'Captcha URL: {captcha_url}')
        req_id, captcha = recognize_captcha(captcha_url)
        retry_count += 1
        if retry_count > 5:
            raise Exception('Retry too many times, aborting...')


    seat_button = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, '考位查询')))
    seat_button.click()
    time.sleep(1)

    # the following two queries must be executed prior to queryTestSeats
    testDays = list(driver.execute_script('return $.getJSON("testDays")'))
    print(f'Test days: {testDays}')
    provinces = driver.execute_script('return $.getJSON("/getTestCenterProvinceCity")')
    print(provinces)

    cities = config['city_list']
    if cities is None:  # null in config means fetching all cities
        cities = []
        for province in provinces:
            for city in provinces['cities']:
                cities.append(city['cityNameEn'])

    vacancies = {}
    earliest_vacancies = {}

    def process_items(items):
        for item in items:
            info = {}
            info["city"] = item.find_element_by_xpath('./td[1]').text
            info["location"] = item.find_element_by_xpath('./td[2]').text
            info["fee"] = item.find_element_by_xpath('./td[3]').text
            info["vacant"] = item.find_element_by_xpath('./td[4]').text != '名额暂满'
            vacancies[city][date].append(info)
            print(info)
            # mark it
            if info["vacant"] and earliest_vacancies[city] is None:
                info["date"] = date
                earliest_vacancies[city] = info

    for city in cities:
        vacancies[city] = {}
        earliest_vacancies[city] = None
        print(f'Checking city {city}')
        for date in testDays:
            vacancies[city][date] = []
            print(f'Test day {date}')
            # crawl by mimicing
            Select(driver.find_element_by_id('centerProvinceCity')).select_by_value(city)
            Select(driver.find_element_by_id('testDays')).select_by_value(date)
            time.sleep(0.5)
            query_button = wait.until(EC.element_to_be_clickable((By.ID, 'btnQuerySeat')))
            while True:
                try:
                    query_button.click()
                    WebDriverWait(driver, 2, 0.1).until(EC.text_to_be_present_in_element((By.XPATH, '//div[@id="qrySeatResult"]/h4'), '考位查询结果'))
                    # will fail for several times
                    break
                except:
                    # retry
                    print('Result not crawled')
                    pass
            items = driver.find_elements_by_xpath('//table[@class="table table-bordered table-striped"][1]/tbody/tr')
            process_items(items)
            try:
                # sometimes there are two exams on one day
                items = driver.find_elements_by_xpath('//table[@class="table table-bordered table-striped"][2]/tbody/tr')
                print('multiple exam times detected')
                process_items(process_items)
            except:
                pass

            # this is not gonna work (so strange)
            # js = 'const callback = arguments[arguments.length - 1]; $.getJSON("testSeat/queryTestSeats",{{city: "{}",testDay: "{}"}}, callback).fail(() => callback("error"))'.format(city, date)
            # print(js)
            # while True:
            #     dataJSON = driver.execute_async_script(js)
            #     if dataJSON == 'error':
            #         print('result not crawled')
            #     else:
            #         print(dataJSON)
            #         break
            
            # if dataJSON is None or not dataJSON['status']:
            #     print(city, date, 'No data fetched')
            #     continue
            # else:
            #     print(city, date, f'Data fetched with')

            # for testTime, testPlaces in dataJSON['testSeats'].items():
            #     for testPlace in testPlaces:
            #         if testPlace['seatStatus'] != 0:
            #             print(f'Found available test seat at {testPlace["cityCn"]} {testPlace["centerNameCn"]}')
            #     # df = pd.DataFrame(dataDetail)
            #     # df['date'] = date
            #     # storage = pd.concat([storage,df],ignore_index=True)
        
            # time.sleep(4.18)

        
    json.dump(vacancies, open(f'data/{datetime.now().strftime("%Y%m%d-%H%M%S")}.json', 'w'), indent=4, ensure_ascii=False)
    return earliest_vacancies


if __name__ == '__main__':
    
    last_earliest = {}
    interval = config['interval']
    time_format = "%Y/%m/%d %H:%M:%S"

    while True:
        try:
            next_time = datetime.now() + timedelta(seconds=interval)
            next_time_str = next_time.strftime(time_format)
            print('Start crawling...')
            earliest_vacancies = crawl_toefl_info()
        
            # format bot message and send
            s = f'爬取时间：{datetime.now().strftime(time_format)}\n'
            s += '最早空余考位'
            if earliest_vacancies != last_earliest:
                notification = True
                s += '（有变化）：\n'
            else:
                notification = False
                s += '（未变化）：\n'

            for city, info in earliest_vacancies.items():
                if info is not None:
                    s += f'{info["city"]}：{info["date"]} {info["location"]}\n'
                else:
                    s += f'{info["city"]}：无\n'
            s += f'fateadm 余额：{fateadm_api.QueryBalc().cust_val}\n'
            s += f'下次爬取时间：{next_time_str}'

            bot.earliest_reply = s
            last_earliest = earliest_vacancies
            message = bot.send_message(s, config['telegram_chat_id'], notification)
            if notification: # ping latest version
                bot.bot.pin_chat_message(chat_id=config['telegram_chat_id'], message_id=message.message_id)
        except:
            traceback.print_exc()
            s = f'Excecption occurred: {traceback.format_exc()})'
            bot.send_message(s, config['telegram_chat_id'])

        print(f'Next crawl time: {next_time_str}')
        delta = next_time - datetime.now()
        time.sleep(delta.seconds)

    driver.quit()
