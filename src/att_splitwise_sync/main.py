from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import undetected_chromedriver as uc
from webdriver_manager.core.os_manager import OperationSystemManager, ChromeType
from time import sleep
import json
import re

from splitwise_api import (
    init_splitwise,
    get_att_group_id,
    get_default_payer_id,
    get_splitwise_mappings,
    create_expense,
    add_account_mapping,
)

def get_chrome_version():
    br_ver = OperationSystemManager().get_browser_version_from_os(ChromeType.GOOGLE)
    return int(br_ver.split('.')[0])

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
        WebDriverWait(driver, timeout=30).until(EC.title_contains('overview'))
    except:
        input("Check browser for successful login to AT&T and then press Enter.")

    # get billing page
    driver.get('https://www.att.com/acctmgmt/billing/mybillingcenter/')

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
        title, _, amount = details[:3]
        
        # add to dues
        dues.append(dict(
            title=title,
            amount=amount.replace('$', ''),
            details='\n'.join(details)
        ))

    # access splitwise API
    session, config = init_splitwise(driver, config)
    
    # get AT&T splitwise group ID
    att_group_id, config = get_att_group_id(session, config)
    
    # get default payer ID
    default_payer_id, config = get_default_payer_id(session, att_group_id, config)
    
    # get account mappings
    splitwise_mappings, config = get_splitwise_mappings(config)

    # build list of users and calculate total cost
    total_cost = 0
    users = []
    user_ids_added = set()
    
    # add default payer with full paid share
    default_payer_paid = sum(float(due['amount']) for due in dues)
    users.append({
        'user_id': default_payer_id,
        'paid_share': str(default_payer_paid),
        'owed_share': '0.00'
    })
    user_ids_added.add(default_payer_id)
    
    # process each due and add users with their owed shares
    period = None
    for due in dues:
        title = due['title']
        amount = float(due['amount'])
        details = due['details']
        period = re.search(r'Monthly charges for (?P<start>.+?) [0-9]{1,2} - (?P<end>.+?) [0-9]{1,2}', details).groupdict()
        total_cost += amount

        # check if splitwise Id exists
        paid_for_id, config = add_account_mapping(session, att_group_id, title, splitwise_mappings, config)
        if paid_for_id is None:
            continue
        
        # add user if not already added
        if paid_for_id not in user_ids_added:
            users.append({
                'user_id': paid_for_id,
                'paid_share': '0.00',
                'owed_share': str(amount)
            })
            user_ids_added.add(paid_for_id)
        else:
            # update owed share if user already exists
            for user in users:
                if user['user_id'] == paid_for_id:
                    user['owed_share'] = str(float(user['owed_share']) + amount)
                    break

    # create single expense with all users
    if users:
        create_expense(session, att_group_id, str(total_cost), users, f'AT&T Bill for {period["end"]}')

    # close driver
    driver.close()


if __name__ == '__main__':
    main()
