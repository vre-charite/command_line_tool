import os.path
import pickle
import json
import re
import datetime
from app.services.file_manager.file_upload import simple_upload, assemble_path
from app.configs.app_config import AppConfig
import app.services.logger_services.log_functions as logger
from app.services.output_manager.error_handler import ECustomizedError, SrvErrorHandler, customized_error_msg
import app.services.output_manager.message_handler as message_handler
from app.services.file_manager.file_manifests import SrvFileManifests
from app.configs.user_config import UserConfig
from app.services.user_authentication.decorator import require_valid_token


class SrvFilePacs:

    class Continue(Exception):
        pass

    def __init__(self, path, upload_event, attribute, result_dir, target_folder, exiting_error):
        self.path = path
        self.upload_event = upload_event
        self.upload_event['current_folder_node'] = '/'.join(upload_event['current_folder_node'].split('/')[0:-1])
        self.manifest = SrvFileManifests(False)
        self.backup_dir = "/etc/pilotcli/.pacs"
        self.prepare_dir()
        self.record_file = f'{self.backup_dir}/.pilot_pacs_record'
        self.project_code = upload_event.get('project_code')
        self.zone = upload_event.get('zone')
        self.attribute = attribute
        self.error = exiting_error
        self.relative_dir = result_dir
        self.target_folder = target_folder
        self.user = UserConfig()

    def prepare_dir(self):
        if not os.path.isdir("/etc/pilotcli"):
            os.makedirs("/etc/pilotcli", mode=0o777)
        if not os.path.isdir("/etc/pilotcli/.pacs"):
            os.makedirs("/etc/pilotcli/.pacs", mode=0o777)

    def update_pacs_result(self, file_location):
        manifest_name = os.path.basename(file_location)
        if os.path.isfile(self.record_file):
            with open(self.record_file, 'rb') as handle:
                exist_record = pickle.load(handle)
                file_list = exist_record.get('ingested_pacs')
                error_list = exist_record.get('ingested_error', [])
                file_list.append(manifest_name)
                result = {'ingested_pacs': sorted(list(set(file_list)), reverse=True),
                          'ingested_error': error_list}
        else:
            result = {'ingested_pacs': [manifest_name]}
        with open(self.record_file, 'wb') as handle:
            pickle.dump(result, handle)

    def read_pacs_data(self):
        if os.path.isfile(self.path):
            SrvErrorHandler.customized_handle(ECustomizedError.INVALID_ACTION, True,
                                              value=': pacs directory must be a folder')
        root, _, files = next(os.walk(self.path))
        new_file_stamp = ''
        new_file_name = []
        try:
            if os.path.isfile(self.record_file):
                with open(self.record_file, 'rb') as handle:
                    exist_record = pickle.load(handle)
                file_list = exist_record.get('ingested_pacs')
                if not file_list:
                    pass
                else:
                    latest_file, ext = os.path.splitext(file_list[0])
                    new_file_stamp = datetime.datetime.strptime(latest_file[8::], "%m%d%Y-%H%M%S")
            for manifest_json in files:
                file_name, ext = os.path.splitext(manifest_json)
                valid_filename = re.match("^([0-9]{8})-([0-9]{6})$", file_name[8::])
                if file_name.startswith('Manifest') and valid_filename:
                    file_stamp = datetime.datetime.strptime(file_name[8::], "%m%d%Y-%H%M%S")
                    if not new_file_stamp:
                        new_file_name.append(manifest_json)
                    elif file_stamp > new_file_stamp:
                        new_file_name.append(manifest_json)
                    else:
                        pass
            if not new_file_name:
                SrvErrorHandler.customized_handle(ECustomizedError.INVALID_ACTION,
                                                  True,
                                                  value=': Pacs only works on new data, no new data found')
            else:
                pass
            file_location = [root.rstrip('/') + '/' + n for n in new_file_name]
            return file_location
        except Exception as e:
            self.recording_error('loading_data', str(e))
            SrvErrorHandler.customized_handle(ECustomizedError.INVALID_PACSDATA, True)

    def recording_error(self, error_type, error_msg, result=''):
        error = {'error_time': datetime.datetime.now().strftime("%m%d%Y-%H%M%S"),
                 'error_type': error_type,
                 'error_msg': error_msg,
                 'error_result': result}
        if os.path.isfile(self.record_file):
            with open(self.record_file, 'rb') as rhandle:
                result = pickle.load(rhandle)
                rhandle.close()
            exist_record = result.get('ingested_error', [])
            exist_record.append(error)
            result['ingested_error'] = exist_record
        else:
            result = {'ingested_pacs': [], 'ingested_error': [error]}
        pickle.dump(result, open(self.record_file, 'wb'))
        SrvErrorHandler.customized_handle(ECustomizedError.INVALID_ACTION, False,
                                          value=f': pacs data process getting {error_type} error: {error_msg}')

    def load_given_manifest(self):
        res = self.manifest.list_manifest(self.project_code)
        attribute_list = res.json().get('result')
        matched_attribute = ''
        for attribute in attribute_list:
            attribute_name = attribute.get('manifest_name')
            if attribute_name == self.attribute:
                matched_attribute = attribute
            else:
                continue
        attributes = {}
        mandatory_attribute = []
        for a in matched_attribute.get('attributes'):
            name = a.get('name')
            optional = a.get('optional')
            attributes[name] = ''
            if not optional:
                mandatory_attribute.append(a.get('name'))
        return attributes, mandatory_attribute



    @require_valid_token()
    def upload_pacs_data(self, data):
        upload_task = self.upload_event.copy()
        for k, v in data.items():
            if k == 'created':
                pass
            else:
                try:
                    data_information = data.get(k)
                    incoming_attribute_template = {}
                    for info_key, info_value in data_information.items():
                        if info_key == 'filePath':
                            path = info_value
                        elif info_key == 'ingested_status' and info_value in ['Terminated', 'Upload_complete', 'Completed']:
                            continue_i = self.Continue()
                            raise continue_i
                        else:
                            incoming_attribute_template[info_key] = info_value
                    if not os.path.isfile(path) and not os.path.isdir(path):
                        SrvErrorHandler.customized_handle(ECustomizedError.INVALID_PATH, False)
                        data[k]['ingested_status'] = 'Terminated'
                        data[k]['ingested_error'] = 'Invalid path'
                        continue
                    current_folder_node, result_file = assemble_path(path, self.target_folder, self.project_code,
                                                                     self.zone, self.user.access_token)
                    result_file = result_file.rstrip('/').lstrip() + '.zip'
                    upload_task['current_folder_node'] = current_folder_node
                    upload_task['file'] = path
                    upload_task['regular_file'] = False
                    upload_task.update({'compress_zip': True})
                    uploaded_file_id = simple_upload(upload_task)
                    attributes, required_field = self.load_given_manifest()
                    if self.attribute:
                        for attribute_name, attribute_value in attributes.items():
                            attributes[attribute_name] = incoming_attribute_template.get(attribute_name, '')
                        attribute_template = {
                            "project_code": upload_task.get('project_code'),
                            "manifest_name": self.attribute,
                            "attributes": attributes
                        }
                        valid_attribute, attribute_error = self.manifest.void_validate_manifest(attribute_template,
                                                                                                False)
                        if valid_attribute[0]:
                            attached_success, attach_error = self.manifest.attach_manifest(attribute_template,
                                                                                           result_file,
                                                                                           self.zone)
                            if attached_success:
                                data[k]['ingested_status'] = 'Completed'
                            else:
                                raise Exception(f"Failed_attach: {attach_error}")
                        else:
                            error_field = valid_attribute[1].get('result').split(' ')
                            data[k]['ingested_status'] = 'Upload_complete'
                            data[k]['ingested_error'] = customized_error_msg(attribute_error) % error_field[-1]
                    elif not uploaded_file_id:
                        data[k]['ingested_status'] = 'Terminated'
                        data[k]['ingested_error'] = 'Failed upload'
                    else:
                        data[k]['ingested_status'] = 'Upload_complete'
                        data[k]['ingested_error'] = 'No attribute attached'
                except self.Continue:
                    continue
                except Exception as e:
                    data[k]['ingested_status'] = 'Terminated'
                    if 'file exist' in str(e):
                        data[k]['ingested_error'] = 'File exist'
                    elif 'Failed_attach:' in str(e):
                        data[k]['ingested_status'] = 'Upload_complete'
                        data[k]['ingested_error'] = str(e).replace('Failed_attach:', '')
                    else:
                        data[k]['ingested_error'] = str(e)
                    SrvErrorHandler.customized_handle(ECustomizedError.INVALID_ACTION, False,
                                                      value=f': pacs data process uploading error: {e}')
        return data

    def update_jsons(self, file, result):
        update_file = open(file, 'w')
        json.dump(result, update_file)
        backup_json = f'{self.backup_dir}/{os.path.basename(file)}'
        with open(backup_json, 'w') as backup_handler:
            json.dump(result, backup_handler)

    def upload_pacs(self):
        try:
            file_location = self.read_pacs_data()
            if self.error:
                raise Exception(self.error)
            for file in file_location:
                logger.info(f"Processing file: {file}")
                file_info = open(file, 'r')
                data = json.load(file_info)
                result = self.upload_pacs_data(data)
                self.update_jsons(file, result)
                self.update_pacs_result(file)
            message_handler.SrvOutPutHandler.pacs_complete()
        except Exception as e:
            self.recording_error('process_error', str(e))
