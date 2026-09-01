import json
import requests
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def save_config(config):
    """Save configuration to config.json"""
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)


def init_splitwise(driver):
    """Initialize Splitwise API session with authentication credentials.
    
    Extracts credentials from the webdriver and initializes a requests Session.
    Returns:
        session: Requests session with authentication
    """
    # Extract user credentials cookie from driver
    driver.get('https://splitwise.com/')
    try:
        WebDriverWait(driver, timeout=30).until(EC.title_contains('Dashboard'))
    except:
        input("Check browser for successful login to Splitwise and then press Enter.")

    cookies = driver.get_cookies()
    user_credentials = None
    for cookie in cookies:
        if cookie['name'] == 'user_credentials':
            user_credentials = cookie['value']
            break
    
    if not user_credentials:
        raise ValueError("user_credentials cookie not found in driver. Please ensure you're logged into Splitwise.")
    
    # Extract CSRF token from the page
    try:
        csrf_token = driver.execute_script(
            "return document.querySelector('[name=\"authenticity_token\"]')?.value || "
            "document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content') || "
            "document.querySelector('[data-csrf-token]')?.getAttribute('data-csrf-token')"
        )
    except:
        csrf_token = None
    
    if not csrf_token:
        raise ValueError("CSRF token not found on page. Please ensure you're on the Splitwise website.")
    
    splitwise_authentication = dict(
        user_credentials=user_credentials,
        csrf_token=csrf_token
    )
    
    # Create a session with the authentication cookies and headers
    session = requests.Session()
    session.headers.update({
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://secure.splitwise.com',
        'referer': 'https://secure.splitwise.com/',
        'x-csrf-token': splitwise_authentication['csrf_token'],
        'x-requested-with': 'XMLHttpRequest',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    })

    # If we have a saved user_credentials value, set it explicitly
    if 'user_credentials' in splitwise_authentication:
        try:
            # prefer the secure.splitwise.com domain when known
            session.cookies.set('user_credentials', splitwise_authentication['user_credentials'], domain='secure.splitwise.com', path='/')
        except Exception:
            session.cookies.set('user_credentials', splitwise_authentication['user_credentials'])

    # Also copy any cookies available in the Selenium driver into the requests session.
    try:
        driver_cookies = driver.get_cookies() if driver is not None else []
        for c in driver_cookies:
            name = c.get('name')
            value = c.get('value')
            domain = c.get('domain')
            path = c.get('path', '/')
            # requests.Session.cookies.set accepts domain/path kwargs; use them when available
            try:
                if domain:
                    session.cookies.set(name, value, domain=domain, path=path)
                else:
                    session.cookies.set(name, value, path=path)
            except Exception:
                # fallback to a simple set if domain/path fail
                session.cookies.set(name, value)
    except Exception:
        # If the driver isn't available or cookies can't be read, continue with what we have
        pass

    return session


def get_att_group_id(session, config):
    """Get or prompt for the AT&T Splitwise group ID.
    
    Returns the group ID and updated config.
    """
    att_group_id = config.get('att_group_id', None)
    if not att_group_id:
        print("AT&T group not specified.")
        print("Pick one from below.")
        
        # Fetch groups from API
        response = session.get('https://secure.splitwise.com/api/v3.0/get_groups')
        groups = response.json()['groups']
        
        for ind, group in enumerate(groups):
            print('%s: %s' % (ind, group['name']))
        
        pick = int(input('Choice: ').strip())
        config['att_group_id'] = groups[pick]['id']
        att_group_id = config['att_group_id']
        save_config(config)
    
    return att_group_id, config


def get_default_payer_id(session, att_group_id, config):
    """Get or prompt for the default payer ID.
    
    Returns the payer ID and updated config.
    """
    default_payer_id = config.get('default_payer_id', None)
    if not default_payer_id:
        print("Default payer not specified.")
        print("Pick one from below.")
        
        # Fetch group details to get members
        response = session.get(f'https://secure.splitwise.com/api/v3.0/get_group/{att_group_id}')
        group = response.json()
        members = group['group']['members']
        
        for ind, member in enumerate(members):
            print('%s: %s' % (ind, member['first_name']))
        
        pick = int(input('Choice: ').strip())
        config['default_payer_id'] = members[pick]['id']
        default_payer_id = config['default_payer_id']
        save_config(config)
    
    return default_payer_id, config


def get_splitwise_mappings(config):
    """Get or initialize splitwise account mappings.
    
    Returns the mappings dictionary and updated config.
    """
    splitwise_mappings = config.get('splitwise_mappings', None)
    if not splitwise_mappings:
        config['splitwise_mappings'] = {}
        splitwise_mappings = config['splitwise_mappings']
        save_config(config)
    
    return splitwise_mappings, config


def create_expense(session, att_group_id, cost, users, description, category_id=18, 
                          currency_code='USD', date=None):
    """Create an unequal expense with multiple users using requests.
    
    Args:
        session: Requests session with authentication
        att_group_id: ID of the group
        cost: Total cost of the expense
        users: List of dictionaries with user_id, paid_share, and owed_share
               Example: [
                   {'user_id': 123, 'paid_share': 100.00, 'owed_share': 25.00},
                   {'user_id': 456, 'paid_share': 0.00, 'owed_share': 25.00},
                   {'user_id': 789, 'paid_share': 0.00, 'owed_share': 25.00},
                   {'user_id': 101, 'paid_share': 0.00, 'owed_share': 25.00}
               ]
        description: Description of the expense
        category_id: Category ID (default 18 for Electricity)
        currency_code: Currency code (default USD)
        date: Optional date for the expense (defaults to today)
    
    Returns:
        The response JSON and error (None if successful)
    """
    # prepare form data
    data = {
        'cost': str(cost),
        'currency_code': currency_code,
        'group_id': str(att_group_id),
        'category_id': str(category_id),
        'description': description,
        'creation_method': 'unequal'
    }
    
    # add date if provided
    if date:
        data['date'] = date
    
    # add all users with their paid and owed shares
    for idx, user_data in enumerate(users):
        data[f'users__{idx}__user_id'] = str(user_data['user_id'])
        data[f'users__{idx}__paid_share'] = str(user_data['paid_share'])
        data[f'users__{idx}__owed_share'] = str(user_data['owed_share'])
    
    # create expense
    response = session.post(
        'https://secure.splitwise.com/api/v3.0/create_expense',
        data=data
    )
    
    if response.status_code != 200:
        print(f"Error creating expense: {response.text}")
        return None, response.text
    
    return response.json(), None


def add_account_mapping(session, att_group_id, title, splitwise_mappings, config):
    """Add or get an account mapping for a title.
    
    Returns the member ID and updated config.
    """
    if title not in splitwise_mappings:
        print("No account mapping for", title)
        print("Pick one from below or leave empty to skip.")
        
        # Fetch group details to get members
        response = session.get(f'https://secure.splitwise.com/api/v3.0/get_group/{att_group_id}')
        group = response.json()
        members = group['group']['members']
        
        for ind, member in enumerate(members):
            print('%s: %s' % (ind, member['first_name']))
        
        pick = input("Choice: ").strip()
        if not pick:
            return None, config
        pick = int(pick)
        splitwise_mappings[title] = members[pick]['id']
        save_config(config)
    
    return splitwise_mappings[title], config