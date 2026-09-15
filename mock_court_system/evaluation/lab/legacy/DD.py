import re
import numpy as np
import os
import sys
import argparse
from . import utils_func as func

class DDEvaluator:
    def __init__(self, args):
        if hasattr(args, 'ground_truth_file') and args.ground_truth_file:
            self.ground_truth = func.load_jsonl(args.ground_truth_file)
        else:
            raise ValueError("ground_truth_file argument must be provided.")
        
        self.args = args
        
        self.dialog_history_dir = args.dialog_history_dir
        self.intermediate_eval = args.intermediate_eval
        self.final_eval = args.final_eval
        
    @staticmethod
    def add_parser_args(parser):
        parser.add_argument("--dialog_history_dir", type = str, required=True)
        parser.add_argument("--intermediate_eval", type = str, required=True)
        parser.add_argument("--final_eval", type = str, required=True)
        parser.add_argument("--ground_truth_file", type = str, required=True)
    
    def _clean(self, text):
        clean_words = ['。', '法定代表人：', '住所：', '住', ' ']
        for word in clean_words:
            text = text.replace(word, '')
        return text
    
    def reformat(self, text, defendant_type):
        defendant_patterns = [
            r"答辩人（?(?:如果是)?(?:自然人|法人|自然人或法人)?）?:?(.*?)\n"
        ]
        defendant_info = None
        for pattern in defendant_patterns:
            match = re.search(pattern, text.replace('*',''), re.DOTALL)
            if match:
                defendant_info = match.group(1).strip()
                break
        if defendant_info is None or len(defendant_info) == 0:
            defendant = text
        else:
            defendant = defendant_info
        
        # 提取答辩意见
        defense_patterns = [
            r"(?:答辩意见|答辩如下|如下答辩|我方提出如下答辩)：\n*?(.*?)(?=\n*(?:此致|证据和证据来源|四、证据及证据|证据|\n*答辩人：|<询问结束>|$))"
        ]
        defense_info = None
        for defense_pattern in defense_patterns:
            defense_info = re.search(defense_pattern, text.replace(' ','').replace('*',''), re.DOTALL)
        if defense_info is None or len(defense_info[0]) == 0:
            defense = text
        else:
            defense = defense_info.group(1).replace(' ','')

        # 提取证据
        evidence_patterns = [
            r"证据和证据来源(?:，证人姓名和住所)?:\n?(.*?)(?=\n{2,}此致|\n{2,}|$)"
        ]
        evidence_info = None
        for evidence_pattern in evidence_patterns:
            evidence_info = re.search(evidence_pattern, text.replace(' ',''), re.DOTALL)
        
        if evidence_info is None or len(evidence_info) == 0:
            evidence = text
        else:
            evidence = evidence_info.group(1).replace(' ','')
                
        model_answer = {
            'defendant': defendant
        }
                
        model_answer['defense'] = defense
        model_answer['evidence'] = evidence
        return model_answer
    
    def compare_defendant(self, defendant_type, ground_truth, model_answer, original_model_answer):
        defendant = ground_truth['specific_characters']['defendant']
        defense = ground_truth['statement_of_defence']
        evidence = ground_truth['evidence']
        
        
        # 统计被告
        model_defence = model_answer['defendant']
        defen = 0
        t_score = 0
        if defendant_type == 'personal':
            gt_name = defendant['name']
            gt_sex = defendant['gender']
            gt_birth = defendant['birth_date']
            gt_address = defendant.get('address')
            gt_ethnicity = defendant.get('ethnicity') or defendant.get('nation')
            if gt_name:
                if gt_name in model_defence:
                    defen += 1
                t_score += 1
            if gt_sex:
                if gt_sex in model_defence and '男/女' not in model_defence:
                    defen += 1
                t_score += 1
            if gt_birth:
                if gt_birth in model_defence:
                    defen += 1
                t_score += 1
            if gt_address:
                if gt_address in model_defence:
                    defen += 1
                t_score += 1
            if gt_ethnicity:
                if gt_ethnicity in model_defence:
                    defen += 1
                t_score += 1
        else:
            gt_name = defendant['name']
            gt_address = defendant['address']
            gt_representative = defendant['representative']
            if gt_name:
                if gt_name in model_defence:
                    defen += 1
                t_score += 1
            if gt_address:
                if gt_address in model_defence:
                    defen += 1
                t_score += 1
            if gt_representative:
                if gt_representative in model_defence:
                    defen += 1
                t_score += 1
        RES_score = defen / t_score if t_score > 0 else 0
        
        # 统计答辩意见
        prompt_defense = '''你是一名法律专家。请根据“法律问题”和“标准答案”，判断“待评测答案”是否完全、准确地涵盖了“标准答案”的所有核心要点，由此给出0-10分的评分。你**不用考虑待评测答案表达是否简洁、重点是否突出、是否使用寒暄语、结构是否冗长等非实质性因素**，无须因不够简洁而扣分。

        标准答案：
        {gt_answer}

        待测评答案：
        {model_answer}
        
        以如下格式输出你的结果（中文括号分割，不要换行，不要带括号）：
        评分：；原因：
        '''
        
        model_defence = model_answer['defense'].replace(' ','')
        full_prompt_defense = prompt_defense.format(gt_answer = defense, model_answer = model_defence)
        try:
            temp = func.get_completion(full_prompt_defense, [], flag=0)[0].split('；')[0].replace('评分：','').replace('分','')
            DEF_score = float(temp)/10
        except:
            # Retry or fallback to 0? Original code retried with original_model_answer
            full_prompt_defense = prompt_defense.format(gt_answer = defense, model_answer = original_model_answer)
            try:
                temp = func.get_completion(full_prompt_defense, [], flag=0)[0].split('；')[0].replace('评分：','').replace('分','')
                DEF_score = float(temp)/10
            except:
                DEF_score = 0
        
        # 统计证据
        prompt_evi = '''你是一名法律专家。请根据“法律问题”和“标准答案”，判断“待评测答案”是否完全、准确地涵盖了“标准答案”的所有核心要点，由此给出0-10分的评分。你**不用考虑待评测答案表达是否简洁、重点是否突出、是否使用寒暄语、结构是否冗长等非实质性因素**，无须因不够简洁而扣分。

        标准答案：
        {gt_answer}

        待测评答案：
        {model_answer}
        
        以如下格式输出你的结果（中文括号分割，不要换行，不要带括号）：
        评分：；原因：
        '''
        
        model_evidence = model_answer['evidence']
        gt_evidences = []
        for de in evidence.keys():
            gt_evidences.append(evidence[de]['evidence'].replace('\n','、'))
        
        evi_scores = 0
        total_evi_scores = 0
        
        if len(gt_evidences) > 0:
            gtevidence = ''
            count = 1
            for gte in gt_evidences:
                gtevidence += f'{count}. {gte}\n'
                count += 1
                
            full_prompt_evi = prompt_evi.format(gt_answer=gtevidence, model_answer=model_evidence)
            try:
                temp = float(func.get_completion(full_prompt_evi, [], flag=0)[0].split('；')[0].replace('评分：','').replace('分',''))/10
            except:
                temp = 0
            evi_scores += temp
            total_evi_scores += 1
        else:
            gtevidence = '无相关证据'
            full_prompt_evi = prompt_evi.format(gt_answer=gtevidence, model_answer=model_evidence)
            try:
                temp = float(func.get_completion(full_prompt_evi, [], flag=0)[0].split('；')[0].replace('评分：','').replace('分',''))/10
            except:
                temp = 0
            evi_scores += temp
            total_evi_scores += 1
        evi_score = evi_scores/total_evi_scores if total_evi_scores > 0 else 0
       
        DOC = {
            "RES": {'RES': RES_score, 'model_RES': model_answer['defendant'], 'ground_truth': defendant},
            "DEF": {'DEF': DEF_score, 'model_DEF': model_defence, 'ground_truth': defense },
            "EVI": {'EVI': evi_score, 'model_EVI': model_evidence, 'ground_truth': gt_evidences, },
            "AVE": np.mean([RES_score, DEF_score, evi_score])
        }
        return DOC
    
    def format_item_names(self, name_set, correct_name, model_defence):
        for item in name_set:
            model_defence = model_defence.replace(item, correct_name)
        return model_defence
    
    def format_following_score(self, model_defence):
        # 名称正确性得分
        label_score = 0
        for i in ['答辩人：', '证据和证据来源，证人姓名和住所：']:
            if i in model_defence:
                label_score += 1
        defense_pattern = r'对(.*?)人民法院（(.*?)）(.*?)民初(.*?)号(.*?)一案的起诉，答辩如下：'
        defense = re.findall(defense_pattern, model_defence)
        if defense != []:
            label_score += 1
        
        # 顺序得分
        incorrect_defendant_names = [
            '答辩人（自然人）：',
            '答辩人（自然人或法人）：',
            '答辩人（如果是自然人）：',
            '答辩人（如果是法人）：',
            '答辩人（法人）：'
            ]
        model_defence = self.format_item_names(incorrect_defendant_names, '答辩人：', model_defence)
        
        last_pos = -1
        for char in ['答辩人：', '答辩如下：', '证据和证据来源，证人姓名和住所：']:
            if char not in model_defence:
                sequential_score = 0
            current_pos = model_defence.find(char, last_pos + 1)
            if current_pos == -1:
                sequential_score = 0
            last_pos = current_pos
        sequential_score = 1

        total_score = sequential_score * (label_score/5)
        FOR = {
            "label_score": label_score,
            "sequential_score": sequential_score,
            "AVE": total_score,
            'model_defence': model_defence
        }
        
        return FOR
    
    def evaluate(self, model, defendant_dh, defendant_type, ground_truth):
        id = defendant_dh['case_id']
        flag = False
        
        dialogs = defendant_dh.get('dialog_history', [])
        if dialogs:
            for dialog in reversed(dialogs):
                content = dialog.get('content', '')
                if dialog['role'] == 'Lawyer' and content is None:
                    flag = False
                    break
                
                if dialog['role'] == 'Lawyer' and '民事答辩状' in str(content) and '答辩人' in str(content):
                    model_defence = content
                    flag = True
                    break
        else:
             model_defence = ""
            
        if not flag:
            print(f'Case {id} unfinished task!')
            evaluation_result = {
                'DOC': {
                    "RES": {'RES_score': 0, 'model_defence': 0, 'ground_truth': 0},
                    "DEF": {'DEF_score': 0, 'model_defence': 0, 'ground_truth': 0 },
                    "EVI": {'evi_score': 0, 'model_evidence': 0, 'ground_truth': 0},
                    "AVE": np.mean([0, 0, 0])
                },
                'FOR': {
                    "label_score": 0,
                    "sequential_score": 0,
                    "FOR": 0,
                    'model_defence': model_defence
                },
                "AVE": np.mean([0, 0]),
                "dialog_history": dialogs
            }
            func.save_json(evaluation_result, os.path.join(self.intermediate_eval,  model, 'DD',  f'{id}.json'))
            return None
        
        model_answer = self.reformat(model_defence, defendant_type)
        DOC = self.compare_defendant(defendant_type, ground_truth, model_answer, model_defence)
        FOR = self.format_following_score(model_defence)
        evaluation_result = {
            "DOC": DOC,
            "FOR": FOR,
            "AVE": np.mean([DOC['AVE'], FOR['AVE']])
        }
        
        func.save_json(evaluation_result, os.path.join(self.intermediate_eval,  model, 'DD',  f'{id}.json'))
    
    def get_final_score(self, intermediate_model_folder, model):
        RES = []
        DEF = []
        EVI = []
        FOR = []
        
        files = [f for f in os.listdir(intermediate_model_folder) if f.endswith('.json')]
        if not files: return

        for file_name in files:
            data = func.load_json(os.path.join(intermediate_model_folder, file_name))
            RES_score = data['DOC']['RES']['RES']
            DEF_score = data['DOC']['DEF']['DEF']
            evi_score = data['DOC']['EVI']['EVI']
            for_score = data['FOR']['AVE']
            RES.append(RES_score)
            DEF.append(DEF_score)
            EVI.append(evi_score)
            FOR.append(for_score)
        print('RES', np.mean(RES))
        print('DEF', np.mean(DEF))
        print('EVI', np.mean(EVI))
        print('FOR', np.mean(FOR)) 
        result = {
            'model': model,
            'RES': np.mean(RES),
            'DEF': np.mean(DEF),
            'EVI': np.mean(EVI),
            'DOC': np.mean([np.mean(RES), np.mean(DEF), np.mean(EVI)]),
            'FOR': np.mean(FOR),
            'AVE': np.mean([np.mean(RES), np.mean(DEF), np.mean(EVI), np.mean(FOR)])
        }
        func.save_json(result, os.path.join(self.final_eval, f'{model}_final.json'))
    
    
    def iterate(self):
        items = os.listdir(self.dialog_history_dir)
        is_nested = any(os.path.isdir(os.path.join(self.dialog_history_dir, i)) for i in items)
        
        if is_nested:
             models = [d for d in items if os.path.isdir(os.path.join(self.dialog_history_dir, d))]
        else:
             models = [os.path.basename(self.dialog_history_dir.rstrip('/\\'))]

        for model in models:
            processed_ids = []
            intermediate_model_folder = os.path.join(self.intermediate_eval,  model, 'DD')
            if not os.path.exists(intermediate_model_folder):
                os.makedirs(intermediate_model_folder)
            
            for file_name in os.listdir(intermediate_model_folder):
                if file_name.endswith('.json'):
                    case_id = file_name.split('-')[-1].replace('.json','')
                    try:
                        processed_ids.append(int(case_id))
                    except: pass
            
            if is_nested:
                jsonl_path = os.path.join(self.dialog_history_dir, model, 'DD_dialog_history.jsonl')
            else:
                jsonl_path = os.path.join(self.dialog_history_dir, 'DD_dialog_history.jsonl')
            
            if not os.path.exists(jsonl_path):
                 print(f"Skipping {model}, file missing: {jsonl_path}")
                 continue

            self.dialog_history = func.load_jsonl(jsonl_path)
            for dh in self.dialog_history:
                case_id = int(dh['case_id'].split('-')[-1].replace('.json',''))
                if case_id not in processed_ids:
                    case_matches = [c for c in self.ground_truth if case_id == int(c['id'].split('-')[-1].replace('.json',''))]
                    if not case_matches:
                        print(f"Ground truth not found for case {case_id}")
                        continue
                    case = case_matches[0]
                    
                    defendant = dh
                    print(f'Evaluating case {case_id}.')
                    
                    if 'specific_characters' in case:
                        defendant_type = 'personal' if 'gender' in case['specific_characters']['defendant'].keys() else 'company'
                    else:
                        defendant_type = 'personal'

                    self.evaluate(model, defendant, defendant_type, case)
                else:
                    print(f'Case {case_id} already evaluated.')
            self.get_final_score(intermediate_model_folder, model)