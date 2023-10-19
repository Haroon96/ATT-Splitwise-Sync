from selenium.webdriver import ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc
from time import sleep
from splitwise import Splitwise
from splitwise.expense import Expense
from splitwise.user import ExpenseUser
import json

def create_expense(sw, att_group_id, paid_by, paid_for, amount, details):
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

def init_driver():
    # add chrome options
    options = uc.ChromeOptions()
    options.headless = False
    options.binary_location = './chrome.app/Contents/MacOS/Google Chrome for Testing'
    driver = uc.Chrome(options=options, version_main=116, user_data_dir='user', use_subprocess=True, executable_path='./chromedriver')
    driver.implicitly_wait(60)
    return driver

def main():
    # load configuration
    with open('configuration.json') as f:
        config = json.load(f)
        auth = config['authentication']

    driver = init_driver()

    # go to login page for att
    driver.get('https://www.att.com/acctmgmt/login')

    # wait for account overview page
    try:
        WebDriverWait(driver, timeout=30).until(EC.title_contains('Overview'))
    except:
        input("Check browser for successful login and then press Enter.")


    driver.get('https://www.att.com/acctmgmt/billandpay')

    # get all bill lines
    lines = driver.find_elements(By.CLASS_NAME, 'OnlineBillDetails__autopay-accordian-main__rmAyb')

    # expand all lines
    for line in lines:
        line.click()
        
    sleep(5)

    dues = []

    for line in lines:
        
        # extract details
        details = line.text.split('\n')
        title, amount = details[:2]
        
        # add to dues
        dues.append(dict(
            title=title,
            amount=amount.replace('$', ''),
            details='\n'.join(details[2:])
        ))

    # access splitwise API
    sw = Splitwise(auth['consumer_key'], auth['consumer_secret'], api_key=auth['api_key'])

    # create splitwise expenses
    att_group_id = config['att_group_id']
    account_mappings = config['sw_account_mapping']
    default_payer_id = config['default_payer_id']

    for due in dues:
        title = due['title']
        amount = due['amount']
        details = due['details']

        # check if splitwise Id exists
        if title not in account_mappings:
            print("No account mapping for", title)
            continue

        # skip payer
        if account_mappings[title] == default_payer_id:
            continue

        # create expense
        paid_for_id = account_mappings[title]
        print('%s owes %s' % (title, amount))
        create_expense(sw, att_group_id, default_payer_id, paid_for_id, amount, details)


    driver.close()


if __name__ == '__main__':
    main()
