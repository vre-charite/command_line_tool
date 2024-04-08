import os

class ENVAR():
    env='prod'
    project = 'vre'
    app_name = 'vreclicli'
    config_path = '{}/.{}cli/'.format(os.environ.get('HOME') or os.environ.get('HOMEPATH'), project)
    dicom_project = 'generate'
    custom_path = 'app/resources'
    base_url = 'https://vre.charite.de/vre/api/vre/'
    service_url = 'https://vre.charite.de/vre/'
    keycloak_url = 'https://vre.charite.de/vre/'
    url_harbor = ''
    harbor_client_secret = ""


