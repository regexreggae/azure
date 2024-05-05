#region ### SYNOPSIS 

#This script updates a range of NSG rules. It only replaces an IP address, nothing else. Useful if you have a dynamic IP at home.
#It assumes that in a given NSG, you have several rules where you use a couple of static IPs that stay the same and one dynamic IP
#that you need to change from time to time

#If you want to use this script you should:
#1.) register an app in Entra ID and note the values (cf. section CORE VARIABLES)
#2.) create an Azure custom RBAC role containing the necessary permissions (I used these, maybe not all of them needed):
# "Microsoft.Network/networkSecurityGroups/read",
# "Microsoft.Network/networkSecurityGroups/write",
# "Microsoft.Network/networkSecurityGroups/securityRules/read",
# "Microsoft.Network/networkSecurityGroups/securityRules/write"
#3.) assign role from 2.) to your app from 1.) at the scope you want (recommendation: low-level scope, I use resource-group level)
#4.) replace all the values in this script with your own ones
#endregion

#region ### IMPORTS
import requests
import base64
#endregion

#region ### FUNCTIONS
def get_access_token(tenant_id, client_id, client_secret):
  """
  Retrieves an access token using the OAuth 2.0 Client Credentials flow.
  """
  url = "https://login.microsoftonline.com/" + tenant_id + "/oauth2/v2.0/token"
  data = {
      "grant_type": "client_credentials",
      "client_id": client_id,
      "scope": "https://management.azure.com/.default",  # Replace with the actual resource scope
      "client_secret": client_secret,
  }
  auth_string = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
  headers = {"Authorization": f"Basic {auth_string}"}
  response = requests.post(url, data=data, headers=headers)
  response.raise_for_status()
  return response.json()["access_token"]

def get_nsg_rule_details(subscription_id, resource_group_name, network_security_group_name, rule_name, access_token):
  """
  Retrieves the details of a network security group rule using a GET request.
  """
  url = (
      f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/"
      f"{resource_group_name}/providers/Microsoft.Network/networkSecurityGroups/"
      f"{network_security_group_name}/securityRules/{rule_name}?api-version=2023-09-01"
  )
  headers = {"Authorization": f"Bearer {access_token}"}
  response = requests.get(url, headers=headers)
  response.raise_for_status()
  rule_details = response.json()
  print(f"Retrieved rule details for: {rule_name}")
  return rule_details

def update_nsg_rule(subscription_id, resource_group_name, network_security_group_name, rule_name, new_rule_props):
  """
  Updates the permitted source IP of a rule within a network security group.
  """
  global access_token
  if not access_token: #if calling this function after another one, e.g. get_nsg_rule_details, we should already have an access token
    access_token = get_access_token(tenant_id, client_id, client_secret)
  url = (
      f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/"
      f"{resource_group_name}/providers/Microsoft.Network/networkSecurityGroups/"
      f"{network_security_group_name}/securityRules/{rule_name}?api-version=2023-09-01"
  )
  headers = {"Authorization": f"Bearer {access_token}"}
  data = {
      "properties": new_rule_props, # we have to pass in the entire dictionary here, replacing only specific props doesn't work!
  }
  response = requests.put(url, headers=headers, json=data)
  response.raise_for_status()
  print(f"Successfully updated NSG rule {rule_name}")
#endregion

#region ### CORE VARIABLES
# Replace the following with your actual values - use inside the script only for debugging, better fetch as env vars or similar!
tenant_id = "your_tenant_id"
client_id = "your_client_id"
client_secret = "your_client_secret"
subscription_id = "your_subscription_id"
resource_group_name = "your_resource_group_name"
network_security_group_name = "your_nsg_name"
rule_names = ["name_of_first_rule", "name_of_second_rule", "name_of_third_rule"]
# some IP stuff identical for all rules
base_ip_list = ['first_static_ip', 'second_static_ip', 'third_static_ip'] # static IPs that are the base and never change. Format can be simply "1.1.1.1" no need to specify mask
home_new_ip = "your_new_ip" # instead of manually putting this in the script, you could pass this as the first argument so a different script could define it etc.
#endregion

#region ### CORE SCRIPT
# Get access token using app credentials
access_token = get_access_token(tenant_id, client_id, client_secret)

## Loop through all existing rules and do the replacements
for rule_name in rule_names:
  # Retrieve rule details
  rule_details = get_nsg_rule_details(subscription_id, resource_group_name, network_security_group_name, rule_name, access_token)
  old_rule_props = rule_details["properties"] #type 'dict'. This whole thing needs to be changed where desired and sent back in a put request!
  print(f"Source IP addresses currently allowed in {rule_name}: {old_rule_props['sourceAddressPrefixes']}")
  
  # Replace old IP by new IP
  old_ip_list = rule_details['properties']['sourceAddressPrefixes'] # currently active list: static IPs + old dynamic IP
  home_old_ip = list(set(old_ip_list) - set(base_ip_list))[0] # extract old dynamic IP
  print(f"Old Home IP is: {home_old_ip}, trying to update with new IP {home_new_ip}") #debug
  new_ip_list = [home_new_ip if ip == home_old_ip else ip for ip in old_ip_list]
  #print(f"The new IP list for our PUT request is this: {new_ip_list}") #debug
  
  # Insert updated IP range to entire props dict
  new_rule_props = old_rule_props.copy()
  new_rule_props["sourceAddressPrefixes"] = new_ip_list
  
  # update the rule
  update_nsg_rule(subscription_id, resource_group_name, network_security_group_name, rule_name, new_rule_props)
#endregion