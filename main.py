#!/usr/bin/env python3

from fateadm_api import FateadmApi

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import traceback
import requests
import sys
import time
import json

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.122 Safari/537.36'

options = Options()
options.add_argument('--headless')
options.add_argument(f'--user-agent="{USER_AGENT}"')

driver = webdriver.Firefox(options=options)

config = json.load(open('config.json'))

fateadm_api = FateadmApi(app_id=None, app_key=None, pd_id=config['fateadm_id'], pd_key=config['fateadm_key'])


def recognize_captcha(image_url):
    res = requests.get(image_url, headers={"User-Agent": USER_AGENT})
    print(res.content)
    captcha_result = fateadm_api.Predict("20400", res.content)
    if captcha_result.ret_code == 0:
        result = captcha_result.pred_rsp.value
        request_id = captcha_result.request_id
        return request_id, result
    else:
        raise Exception(f'Captcha API request failed: {captcha_result.ret_code} {captcha_result.err_msg}')


def fill_credentials():
    input_name = wait.until(EC.presence_of_element_located((By.ID, 'userName')))
    input_name.clear()
    input_name.send_keys(config['neea_username'])
    input_password = wait.until(EC.presence_of_element_located((By.ID, 'textPassword')))
    input_password.clear()
    input_password.send_keys(config['3qbf3q#m*K2Cr5RKOvpS'])


def get_captcha():
    input_captcha = wait.until(EC.presence_of_element_located((By.ID, 'verifyCode')))
    input_captcha.click()
    captcha_img = wait.until((EC.presence_of_element_located(By.ID, "chkImg")))
    captcha_url = driver.find_element_by_id('chkImg').getAttribute("src")
    return captcha_url


def fill_captcha_and_login(captcha):
    input_captcha = wait.until(EC.presence_of_element_located((By.ID, 'verifyCode')))
    input_captcha.clear()
    input_captcha.send_keys(captcha)
    submit_button = wait.until(EC.presence_of_element_located((By.ID, 'btnLogin')))
    submit_button.click()
    try:
        wait.until(EC.text_to_be_present_in_element(By.XPATH, '//div[@class="myhome_info_cn"]/span[2]'), '21073302')
        return True
    except:
        return False


if __name__ == '__main__':

    # print(fateadm_api.QueryBalc().cust_val)

    driver.get('https://toefl.neea.cn/login')
    wait = WebDriverWait(driver, 20, 0.5)

    # login process
    try:
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
            if retry_count > 10:
                raise Exception('Retry too many times, aborting...')

    except Exception as e:
        traceback.print_exc()
        driver.quit()
        sys.exit(1)


    testDays = list(driver.execute_script('return $.getJSON("testDays")'))
    print(f'Test days: {testDays}')

    cities = config['city_list']
    if cities is None:  # null in config means fetching all cities
        provinces = driver.execute_script('return $.getJSON("/getTestCenterProvinceCity")')
        print(provinces)
        cities = []
        for province in provinces:
            for city in provinces['cities']:
                cities.append(city['cityNameEn'])

    for city in cities:
        print(f'Checking city {city}')
        for date in testDays:
            print(f'Test day {date}')
            js = 'return $.getJSON("testSeat/queryTestSeats",{city: "{}",testDay: "{}"});'.format(city, date)
            dataJSON = driver.execute_script(js)
            
            if dataJSON is None or not dataJSON['status']:
                print(city, date, 'No data fetched')
                continue
            else:
                print(city, date, f'Data fetched with')

            for testTime, testPlaces in dataJSON['testSeats'].items():
                for testPlace in testPlaces:
                    if testPlace['seatStatus'] != 0:
                        print(f'Found available test seat at {testPlace["cityCn"]} {testPlace["centerNameCn"]}')
                # df = pd.DataFrame(dataDetail)
                # df['date'] = date
                # storage = pd.concat([storage,df],ignore_index=True)
        
            time.sleep(4.18)

    driver.quit()

