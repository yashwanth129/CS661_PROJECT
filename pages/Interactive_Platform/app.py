from flask import Flask, render_template, jsonify, request
import pandas as pd
import json
import numpy as np

app = Flask(__name__)
EXCLUDED_DISEASE_IDS = {1058, 1029, 1026, 1027, 1028, 1059, 294}
def filter_disease_hierarchy(causes):
    filtered_causes = []
    for cause in causes:
        if int(cause['id']) not in EXCLUDED_DISEASE_IDS:
            if 'subcauses' in cause:
                cause['subcauses'] = filter_disease_hierarchy(cause['subcauses'])
            filtered_causes.append(cause)
    return filtered_causes

def load_data():
    with open('data/filtered_hierarchical_causes.json', 'r') as f:
        disease_hierarchy = json.load(f)
    
    disease_hierarchy['causes'] = filter_disease_hierarchy(disease_hierarchy['causes'])
    location_mapping = pd.read_csv('../location_mapping.csv')
    location_dict = dict(zip(location_mapping['location_id'], location_mapping['location_name']))
    location_dict[169]="Central African Rep."
    location_dict[12]="Laos"
    location_dict[20]="Vietnam"
    location_dict[7]="North Korea"
    location_dict[68]="South Korea"
    location_dict[155]="Turkey"
    location_dict[28]="Solomon Is."
    location_dict[44]="Bosnia and Herz."
    
    gbd_data = pd.read_csv('../GBD.csv',usecols=['location_id', 'cause_id', 'sex_id', 'year', 'metric_name', 'val'])
    gbd_data = gbd_data[~gbd_data['cause_id'].isin(EXCLUDED_DISEASE_IDS)]
    rate_data = gbd_data[gbd_data['metric_name'] == 'Rate']
    available_years = sorted(rate_data['year'].unique())
    available_years = [int(year) for year in available_years]
    return disease_hierarchy, location_dict, rate_data, available_years

disease_hierarchy, location_dict, rate_data, available_years = load_data()

class TreeNode:
    def __init__(self, disease_id, disease_name, parent_id=None):
        self.disease_id = disease_id
        self.disease_name = disease_name
        self.parent_id = parent_id
        self.value = 0
        self.taken = False
        self.children = []
        self.parent = None

    def add_child(self, child_node):
        self.children.append(child_node)
        child_node.parent = self

    def __repr__(self):
        return f"TreeNode(id={self.disease_id}, name={self.disease_name})"
class DiseaseTree:
    def __init__(self):
        self.nodes = {}
        self.root_nodes = []

    def build_from_json(self, cause_list, parent_id=None):
        for cause in cause_list:
            node = TreeNode(disease_id=cause["id"], disease_name=cause["name"], parent_id=parent_id)
            self.nodes[node.disease_id] = node
            if parent_id is not None:
                parent_node = self.nodes[parent_id]
                parent_node.add_child(node)
            else:
                self.root_nodes.append(node)
            if "subcauses" in cause:
                self.build_from_json(cause["subcauses"], parent_id=node.disease_id)

    def reset_all_values(self):
        new_set = {}
        for id, node in self.nodes.items():
            node.value = 0
            node.taken = False
            new_set[id]=node
        self.nodes=new_set
    def get_node(self, disease_id):
        return self.nodes.get(disease_id)
    
    def update_value(self, disease_id, value, taken=None):
        node = self.get_node(disease_id)
        node.value=value
        if taken!=None:
            node.taken=taken
        self.nodes[disease_id] = node

    def __repr__(self):
        return f"DiseaseTree({len(self.nodes)} nodes)"

dtree = DiseaseTree()
dtree.build_from_json(disease_hierarchy["causes"])

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/diseases')
def get_diseases():
    return jsonify(disease_hierarchy)

@app.route('/api/locations')
def get_locations():
    return jsonify(location_dict)

@app.route('/api/years')
def get_years():
    return jsonify(available_years)

def expand_disease_ids(disease_ids):
    expanded_ids = set(disease_ids)
    
    def add_children(disease_id, causes):
        for cause in causes:
            if int(cause['id']) == disease_id:
                if 'subcauses' in cause and cause['subcauses']:
                    for subcause in cause['subcauses']:
                        subcause_id = int(subcause['id'])
                        expanded_ids.add(subcause_id)
                        if 'subcauses' in subcause and subcause['subcauses']:
                            add_children(subcause_id, [subcause])
                return
            if 'subcauses' in cause and cause['subcauses']:
                add_children(disease_id, cause['subcauses'])
    
    for disease_id in list(disease_ids):
        add_children(disease_id, disease_hierarchy['causes'])
    
    return list(expanded_ids)

def expand_disease_leaf_ids(disease_ids):
    expanded_ids = set()
    # print("disease_ids",disease_ids)
    def add_children(disease_id, causes):
        # print("add_children", end=" | ")
        # print("disease_id",disease_id, end=" | ")
        for cause in causes:
            if int(cause['id']) == disease_id:
                if 'subcauses' in cause and cause['subcauses']:
                    for subcause in cause['subcauses']:
                        subcause_id = int(subcause['id'])
                        if 'subcauses' in subcause and subcause['subcauses']:
                            add_children(subcause_id, [subcause])
                        else:
                            subcause_id = int(subcause['id'])
                            expanded_ids.add(subcause_id)
                else:
                    subcause_id = int(cause['id'])
                    expanded_ids.add(subcause_id)
                return
            if 'subcauses' in cause and cause['subcauses']:
                add_children(disease_id, cause['subcauses'])
            elif int(cause['id']) == disease_id:
                subcause_id = int(cause['id'])
                expanded_ids.add(subcause_id)
    for disease_id in list(disease_ids):
        add_children(disease_id, disease_hierarchy['causes'])
    return list(expanded_ids)


@app.route('/api/country-history')
def get_country_history():
    location_id = request.args.get('location', '')
    diseases = request.args.get('diseases', '')
    sexes = request.args.get('sexes', '1,2')
    if not location_id:
        return jsonify({})
    disease_ids = [int(d) for d in diseases.split(',') if d] if diseases else []
    sex_ids = [int(s) for s in sexes.split(',') if s] if sexes else [1, 2]
    if disease_ids:
        disease_ids = expand_disease_leaf_ids(disease_ids)
    filtered_data = rate_data[ (rate_data['location_id'] == int(location_id)) & (rate_data['sex_id'].isin(sex_ids)) ]
    if disease_ids:
        filtered_data = filtered_data[filtered_data['cause_id'].isin(disease_ids)]
    result = {}
    total_by_year = filtered_data.groupby('year')['val'].sum().reset_index()
    result['total'] = {str(int(row['year'])): float(row['val']) for _, row in total_by_year.iterrows()}
    return jsonify(result)

@app.route('/api/all-years-data')
def get_all_years_data():
    diseases = request.args.get('diseases', '')
    sexes = request.args.get('sexes', '1,2')
    disease_ids = [int(d) for d in diseases.split(',') if d] if diseases else []
    sex_ids = [int(s) for s in sexes.split(',') if s] if sexes else [1, 2]
    if disease_ids:
        disease_ids = expand_disease_leaf_ids(disease_ids)
    filtered_data = rate_data[rate_data['sex_id'].isin(sex_ids)]
    if disease_ids:
        filtered_data = filtered_data[filtered_data['cause_id'].isin(disease_ids)]
    result = {}
    stats = {}
    for year in available_years:
        year_str = str(year)
        year_data = filtered_data[filtered_data['year'] == year]
        if year_data.empty:
            continue
        year_result = {}
        country_totals = year_data.groupby('location_id')['val'].sum().reset_index()
        for _, row in country_totals.iterrows():
            location_id = str(int(row['location_id']))
            val = float(row['val'])
            if val > 0:
                if location_id not in year_result:
                    year_result[location_id] = {}
                year_result[location_id]['total'] = val
        sex_data = year_data.groupby(['location_id', 'sex_id'])['val'].sum().reset_index()
        for _, row in sex_data.iterrows():
            location_id = str(int(row['location_id']))
            sex_id = str(int(row['sex_id']))
            val = float(row['val'])
            if val > 0:
                if location_id not in year_result:
                    year_result[location_id] = {}
                year_result[location_id][sex_id] = val
        totals = [data.get('total', 0) for data in year_result.values()]
        if totals:
            stats[year_str] = {'min': float(min(totals)) if totals else 0,'max': float(max(totals)) if totals else 0,'mean': float(np.mean(totals)) if totals else 0}
        else:
            stats[year_str] = {'min': 0, 'max': 0, 'mean': 0}
        result[year_str] = year_result
    return jsonify({'yearData': result,'statistics': stats})

@app.route('/api/all-countries-rates')
def get_all_countries_rates():
    year = int(request.args.get('year', available_years[-1]))
    diseases = request.args.get('diseases', '')
    sexes = request.args.get('sexes', '1,2')
    disease_ids = [int(d) for d in diseases.split(',') if d] if diseases else []
    sex_ids = [int(s) for s in sexes.split(',') if s] if sexes else [1, 2]
    if disease_ids:
        disease_ids = expand_disease_leaf_ids(disease_ids)
    # print("disease_ids",disease_ids)
    filtered_data = rate_data[ (rate_data['year'] == year) & (rate_data['sex_id'].isin(sex_ids)) ]
    if disease_ids:
        filtered_data = filtered_data[filtered_data['cause_id'].isin(disease_ids)]
    result = {}
    aggregated_data = filtered_data.groupby(['location_id', 'sex_id'])['val'].sum().reset_index()
    for _, row in aggregated_data.iterrows():
        location_id = str(int(row['location_id']))
        sex_id = str(int(row['sex_id']))
        val = float(row['val'])
        # print(row)
        if location_id not in result:
            result[location_id] = {}
        result[location_id][sex_id] = val
    total_rates = filtered_data.groupby('location_id')['val'].sum().reset_index()
    rates = []
    for _, row in total_rates.iterrows():
        location_id = str(int(row['location_id']))
        total = float(row['val'])
        if location_id not in result:
            result[location_id] = {}
        result[location_id]['total'] = total
        rates.append(total)
    if rates:
        result['_statistics'] = {'min': float(min(rates)),'max': float(max(rates)),'mean': float(np.mean(rates))}
    else:
        result['_statistics'] = {'min': 0,'max': 0,'mean': 0}
    return jsonify(result)

@app.route('/country/<location_id>')
def country_detail(location_id):
    try:
        location_id = int(location_id)
        country_name = location_dict.get(location_id, "Unknown Country")
    except ValueError:
        country_name = "Unknown Country"
    return render_template('country_detail.html', location_id=location_id,country_name=country_name)

@app.route('/api/disease-rates-by-level1')
def get_disease_rates_by_level1():
    location_id = request.args.get('location', '')
    diseases = request.args.get('diseases', '')
    sexes = request.args.get('sexes', '1,2')
    if not location_id:
        return jsonify({})
    disease_ids = [int(d) for d in diseases.split(',') if d] if diseases else []
    sex_ids = [int(s) for s in sexes.split(',') if s] if sexes else [1, 2]
    level1_mapping = {}
    level1_names = {}

    def map_diseases_to_level1(causes, parent_id=None):
        for cause in causes:
            cause_id = int(cause['id'])
            cause_code = cause.get('cause', '')
            is_level1 = cause_code and len(cause_code) == 1
            if is_level1:
                level1_mapping[cause_id] = cause_id
                level1_names[cause_id] = cause['name']
                current_parent = cause_id
            else:
                if parent_id:
                    level1_mapping[cause_id] = parent_id
                current_parent = parent_id
            if 'subcauses' in cause and cause['subcauses']:
                map_diseases_to_level1(cause['subcauses'], current_parent)
    map_diseases_to_level1(disease_hierarchy['causes'])
    filtered_data = rate_data[ (rate_data['location_id'] == int(location_id)) & (rate_data['sex_id'].isin(sex_ids)) ]
    if disease_ids:
        expanded_ids = expand_disease_leaf_ids(disease_ids)
        filtered_data = filtered_data[filtered_data['cause_id'].isin(expanded_ids)]
    result = {}
    for _, row in filtered_data.iterrows():
        year = str(int(row['year']))
        disease_id = int(row['cause_id'])
        sex_id = str(int(row['sex_id']))
        val = float(row['val'])
        if disease_id not in level1_mapping:
            continue
        level1_id = level1_mapping[disease_id]
        if level1_id not in disease_ids and disease_id not in disease_ids:
            continue
        if level1_id not in result:
            result[level1_id] = {'name': level1_names.get(level1_id, f"Disease {level1_id}"),'data': {}}
        if year not in result[level1_id]['data']:
            result[level1_id]['data'][year] = {}
        if 'total' not in result[level1_id]['data'][year]:
            result[level1_id]['data'][year]['total'] = 0
        if sex_id not in result[level1_id]['data'][year]:
            result[level1_id]['data'][year][sex_id] = 0
        result[level1_id]['data'][year][sex_id] += val
        result[level1_id]['data'][year]['total'] += val
    return jsonify(result)

@app.route('/disease_drilldown/<location_id>/<year>/<disease_id>')
def disease_drilldown(location_id, year, disease_id):
    try:
        location_id = int(location_id)
        year = int(year)
        disease_id = int(disease_id)
        country_name = location_dict.get(location_id, "Unknown Country")
        disease_name = get_disease_name(disease_id)
    except (ValueError, TypeError):
        country_name = "Unknown Country"
        disease_name = "Unknown Disease"
    diseases = request.args.get('diseases', '')
    sexes = request.args.get('sexes', '1,2')
    if not all([year, location_id]):
        return jsonify({"error": "Missing required parameters"})
    try:
        disease_ids = [int(d) for d in diseases.split(',') if d] if diseases else []
        sex_ids = [int(s) for s in sexes.split(',') if s] if sexes else [1, 2]
    except ValueError:
        return jsonify({"error": "Invalid parameter format"})
    update_dtree(disease_ids, location_id, sex_ids, year)
    return render_template('disease_drilldown.html',location_id=location_id, country_name=country_name,year=year,disease_id=disease_id, disease_name=disease_name)

def get_disease_name(disease_id):
    def find_disease(causes, target_id):
        for cause in causes:
            if int(cause['id']) == target_id:
                return cause['name']
            if 'subcauses' in cause and cause['subcauses']:
                result = find_disease(cause['subcauses'], target_id)
                if result:
                    return result
        return None
    return find_disease(disease_hierarchy['causes'], disease_id) or "Unknown Disease"

@app.route('/api/disease_children')
def get_disease_children():
    parent_id = request.args.get('parent_id')
    year = request.args.get('year')
    location_id = request.args.get('location_id')
    if not all([parent_id, year, location_id]):
        return jsonify({"error": "Missing required parameters"})
    try:
        parent_id = int(parent_id)
        year = int(year)
        location_id = int(location_id)
    except ValueError:
        return jsonify({"error": "Invalid parameter format"})

    def find_children(causes, target_id):
        node = dtree.get_node(target_id)
        return node.children
    children_ids = find_children(disease_hierarchy['causes'], parent_id)
    if not children_ids:
        return jsonify([])
    # print(children_ids)
    result = []
    for child_node in children_ids:
        child_id = child_node.disease_id
        if child_id == None:
            continue
        node = dtree.get_node(child_id)
        child_rate = node.value
        if node.taken==False and child_rate==0:
            continue
        result.append({"id": child_id,"name": node.disease_name,"cause_code": "","has_children": False if len(node.children)==0 else True,"value": child_rate})
    return jsonify(result)

@app.route('/api/disease_details')
def get_disease_details():
    disease_id = request.args.get('disease_id')
    year = request.args.get('year')
    location_id = request.args.get('location_id')
    sexes = request.args.get('sexes', '1,2')
    if not all([disease_id, year, location_id]):
        return jsonify({"error": "Missing required parameters"})
    try:
        disease_id = int(disease_id)
        year = int(year)
        location_id = int(location_id)
        sex_ids = [int(s) for s in sexes.split(',') if s] if sexes else [1, 2]
    except ValueError:
        return jsonify({"error": "Invalid parameter format"})
    
    def find_disease(causes, target_id):
        for cause in causes:
            if int(cause['id']) == target_id:
                has_children = 'subcauses' in cause and len(cause['subcauses']) > 0
                return {"id": target_id,"name": cause['name'],"cause_code": cause.get('cause', ''),"has_children": has_children}
            if 'subcauses' in cause and cause['subcauses']:
                result = find_disease(cause['subcauses'], target_id)
                if result:
                    return result
        return None
    disease_info = find_disease(disease_hierarchy['causes'], disease_id)
    if not disease_info:
        return jsonify({"error": "Disease not found"})
    filtered_data = rate_data[(rate_data['location_id'] == location_id) & (rate_data['year'] == year) & (rate_data['cause_id'] == disease_id) & (rate_data['sex_id'].isin(sex_ids)) ]
    rates = {"total": 0}
    if not filtered_data.empty:
        total_rate = float(filtered_data['val'].sum())
        rates["total"] = total_rate
        for sex_id in sex_ids:
            sex_data = filtered_data[filtered_data['sex_id'] == sex_id]
            if not sex_data.empty:
                rates[str(sex_id)] = float(sex_data['val'].sum())
            else:
                rates[str(sex_id)] = 0
    result = {**disease_info,"rates": rates,"country_name": location_dict.get(location_id, "Unknown Country"),"year": year}
    return jsonify(result)

def set_as_taken_dtree(diseases_ids, values):
    # print(diseases_ids, values)
    for id in diseases_ids:
        node = dtree.get_node(id)
        node.taken=True
        value = values[id]
        dtree.update_value(id, value, taken=True)
        node.value = value

def add_untill_taken(diseases_ids, values):
    # print(diseases_ids, values)
    def go_up(id, val):
        # print(f"go_up|| id:{id}, val:{val} ")
        if id == None:
            return
        node = dtree.get_node(id)
        if node.taken==True:
            return
        node.value = node.value + val
        dtree.update_value(id, node.value)
        # print("node.value", node.value)
        go_up(node.parent_id, val) 

    for id in diseases_ids:
        node = dtree.get_node(id)
        go_up(node.parent_id,values[id])

def update_dtree(disease_ids,location_id,sex_ids,  year):
    # print("update_dtree")
    filtered_data = rate_data[ (rate_data['location_id'] == location_id) & (rate_data['year'] == year) & (rate_data['sex_id'].isin(sex_ids)) ]
    dtree.reset_all_values()
    values={}
    expanded_ids = expand_disease_ids(disease_ids)
    for id in expanded_ids:
        disease_data = filtered_data[filtered_data['cause_id'] == id]
        values[id]=float(disease_data['val'].sum()) if not disease_data.empty else 0
    set_as_taken_dtree(expanded_ids, values)
    add_untill_taken(expanded_ids, values)

@app.route('/api/hierarchical-disease-data')
def get_hierarchical_disease_data():
    year = request.args.get('year')
    location_id = request.args.get('location')
    diseases = request.args.get('diseases', '')
    sexes = request.args.get('sexes', '1,2')
    if not all([year, location_id]):
        return jsonify({"error": "Missing required parameters"})
    try:
        year = int(year)
        location_id = int(location_id)
        disease_ids = [int(d) for d in diseases.split(',') if d] if diseases else []
        sex_ids = [int(s) for s in sexes.split(',') if s] if sexes else [1, 2]
    except ValueError:
        return jsonify({"error": "Invalid parameter format"})
    if disease_ids:
        expanded_ids = expand_disease_ids(disease_ids)
    else:
        expanded_ids = []
    filtered_data = rate_data[ (rate_data['location_id'] == location_id) & (rate_data['year'] == year) & (rate_data['sex_id'].isin(sex_ids)) ]
    if expanded_ids:
        filtered_data = filtered_data[filtered_data['cause_id'].isin(expanded_ids)]
    sunburst_data = []
    sunburst_data.append({"id": "root","name": "All Diseases","parent": "","value": 0})

    def process_disease(disease_id, parent_id):
        node = dtree.get_node(disease_id)
        value = node.value
        # print(f"value:{value}")
        if node.taken==False and value==0:
            return
        sunburst_data.append({"id": str(disease_id), "name": node.disease_name, "parent": parent_id, "value": value })
        for child in node.children:
            process_disease(child.disease_id, str(disease_id) )
    update_dtree(disease_ids, location_id, sex_ids, year)
    for cause in disease_hierarchy['causes']:
        process_disease( int(cause['id']), "root")
    total_value = sum(item["value"] for item in sunburst_data if item["parent"] == "root")
    sunburst_data[0]["value"] = total_value
    return jsonify(sunburst_data)

if __name__ == '__main__':
    app.run(debug=True,port=5000)
