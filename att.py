#!/usr/bin/env python
# coding: utf-8

from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc
from time import sleep
from splitwise import Splitwise
from splitwise.expense import Expense
from splitwise.user import ExpenseUser
import json

with open('configuration.json') as f:
    config = json.load(f)
    auth = config['authentication']

options = ChromeOptions()
options.add_argument('--user-data-dir=user')
options.add_argument('--window-size=640,480')
driver = uc.Chrome(options=options)
driver.implicitly_wait(60)

driver.get('https://www.att.com/acctmgmt/login')

try:
    WebDriverWait(driver, timeout=30).until(EC.url_contains('accountoverview'))
except:
    input("Check browser for successful login and then press Enter.")


dues = []
driver.get('https://www.att.com/acctmgmt/billandpay')

# get all bill lines
lines = driver.find_elements(By.CLASS_NAME, 'OnlineBillDetails__autopay-accordian-main__rmAyb')

for line in lines:
    line.click()
    
sleep(5)

for line in lines:
    for el in line.find_elements(By.CLASS_NAME, 'BillSection__cursor-pointer__3FVip'):
        el.click()
    
    details = line.text.split('\n')
    title, amount = details[:2]
    
    dues.append(dict(
        title=title,
        amount=amount.replace('$', ''),
        details='\n'.join(details[2:])
    ))



sw = Splitwise(auth['consumer_key'], auth['consumer_secret'], api_key=auth['api_key'])

def create_expense(att_group_id, paid_by, paid_for, amount, details):
    expense = Expense()
    expense.setGroupId(att_group_id)
    expense.setCost(amount)
    expense.setDescription("AT&T")
    expense.setDetails(details)
    
    paid_by_user = ExpenseUser()
    paid_by_user.setId(paid_by)
    
    paid_for_user = ExpenseUser()
    paid_for_user.setId(paid_for)
    
    paid_by_user.setPaidShare(amount)
    paid_by_user.setOwedShare('0.00')
    
    paid_for_user.setPaidShare('0.00')
    paid_for_user.setOwedShare(amount)
    
    expense.addUser(paid_by_user)
    expense.addUser(paid_for_user)
    
    nExpense, error = sw.createExpense(expense)
    if error is not None:
        print(error.getErrors())


att_group_id = config['att_group_id']
account_mappings = config['sw_account_mapping']
default_payer_id = config['default_payer_id']

for due in dues:
    title = due['title']
    amount = due['amount']
    details = due['details']
    if title not in account_mappings:
        print("No account mapping for", title)
        continue
    if account_mappings[title] == default_payer_id:
        continue
    paid_for_id = account_mappings[title]
    print('%s owes %s' % (title, amount))
    create_expense(att_group_id, default_payer_id, paid_for_id, amount, details)


driver.close()
