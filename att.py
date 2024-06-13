from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc
from webdriver_manager.core.os_manager import OperationSystemManager, ChromeType
from time import sleep
from splitwise import Splitwise
from splitwise.expense import Expense
from splitwise.user import ExpenseUser
import json

def save_config(config):
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)

def get_chrome_version():
    br_ver = OperationSystemManager().get_browser_version_from_os(ChromeType.GOOGLE)
    return int(br_ver.split('.')[0])

def create_expense(sw, att_group_id, paid_by, paid_for, amount, details):
    # create expense object
    expense = Expense()
    expense.setGroupId(att_group_id)
    expense.setCost(amount)
    expense.setDescription("AT&T")
    expense.setDetails(details)
    
    # add information about who paid
    paid_by_user = ExpenseUser()
    paid_by_user.setId(paid_by)
    
    # add information about who pays
    paid_for_user = ExpenseUser()
    paid_for_user.setId(paid_for)
    
    # set payment amounts for who paid
    paid_by_user.setPaidShare(amount)
    paid_by_user.setOwedShare('0.00')
    
    # set payment amount for who pays
    paid_for_user.setPaidShare('0.00')
    paid_for_user.setOwedShare(amount)
    
    # add users to expense entry
    expense.addUser(paid_by_user)
    expense.addUser(paid_for_user)
    
    # create expense
    nExpense, error = sw.createExpense(expense)
    if error is not None:
        print(error.getErrors())

def init_driver():
    # add chrome options
    options = uc.ChromeOptions()
    driver = uc.Chrome(options=options, user_data_dir='user', use_subprocess=True, version_main=get_chrome_version())
    driver.implicitly_wait(60)
    return driver

def main():
    # load configuration
    try:
        with open('config.json') as f:
            config = json.load(f)
    except:
        config = {}

    # init driver
    driver = init_driver()

    # go to login page for att
    driver.get('https://www.att.com/acctmgmt/login')

    # click on first user ID
    try:
        driver.find_element(By.ID, 'savedUserUserButton0').click()
    except:
        pass

    # wait for account overview page
    try:
        WebDriverWait(driver, timeout=30).until(EC.title_contains('Overview'))
    except:
        input("Check browser for successful login and then press Enter.")


    # get billing page
    driver.get('https://www.att.com/acctmgmt/billandpay')

    # get all bill lines
    lines = driver.find_elements(By.CSS_SELECTOR, 'div:has(> [data-testid="service-accordion-button"])')

    # wait 5 seconds for lines to be expandable
    sleep(5)
    
    # expand all lines
    for line in lines:
        line.click()
        
    # get due amounts from AT&T
    dues = []
    for line in lines:
        
        # extract details
        details = line.text.split('\n')
        title, number, amount = details[:3]
        
        # add to dues
        dues.append(dict(
            title=title,
            amount=amount.replace('$', ''),
            details='\n'.join(details)
        ))

    # access splitwise API
    splitwise_authentication = config.get('splitwise_authentication', None)
    if not splitwise_authentication:
        print("Splitwise authentication not found. Please follow the URL below to create a new app and enter the details below.")
        print("https://secure.splitwise.com/apps/")
        config['splitwise_authentication'] = dict(
            consumer_key=input("Consumer key >").strip(),
            consumer_secret=input("Consumer secret >").strip(),
            api_key=input("API key >").strip()
        )
        splitwise_authentication = config['splitwise_authentication']
        save_config(config)
        
    sw = Splitwise(
        consumer_key=splitwise_authentication['consumer_key'], 
        consumer_secret=splitwise_authentication['consumer_secret'], 
        api_key=splitwise_authentication['api_key']
    )

    # get AT&T splitwise group ID
    att_group_id = config.get('att_group_id', None)
    if not att_group_id:
        print("AT&T group not specified.")
        print("Pick one from below.")
        groups = sw.getGroups()
        for ind, group in enumerate(groups):
            print('%s: %s' % (ind, group.getName()))
        pick = int(input('Choice: ').strip())
        config['att_group_id'] = groups[pick].getId()
        att_group_id = config['att_group_id']
        save_config(config)

    # get default payer ID
    default_payer_id = config.get('default_payer_id', None)
    if not default_payer_id:
        print("Default payer not specified.")
        print("Pick one from below.")
        members = sw.getGroup(att_group_id).getMembers()
        for ind, member in enumerate(members):
            print('%s: %s' % (ind, member.getFirstName()))
        pick = int(input('Choice: ').strip())
        config['default_payer_id'] = members[pick].getId()
        default_payer_id = config['default_payer_id']
        save_config(config)

    # get account mappings
    splitwise_mappings = config.get('splitwise_mappings', None)
    if not splitwise_mappings:
        config['splitwise_mappings'] = {}
        splitwise_mappings = config['splitwise_mappings']
        save_config(config)

    # create expenses on splitwise
    for due in dues:
        title = due['title']
        amount = due['amount']
        details = due['details']

        # check if splitwise Id exists
        if title not in splitwise_mappings:
            print("No account mapping for", title)
            print("Pick one from below.")
            members = sw.getGroup(att_group_id).getMembers()
            for ind, member in enumerate(members):
                print('%s: %s' % (ind, member.getFirstName()))
            pick = int(input('Choice: ').strip())
            splitwise_mappings[title] = members[pick].getId()
            save_config(config)
        
        # skip default payer
        if splitwise_mappings[title] == default_payer_id:
            continue

        # create expense
        paid_for_id = splitwise_mappings[title]
        print('%s owes %s' % (title, amount))
        create_expense(sw, att_group_id, default_payer_id, paid_for_id, amount, details)

    # close driver
    driver.close()


if __name__ == '__main__':
    main()
