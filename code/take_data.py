import WriteData
import json
import random
import re
import ast
from typing import List, Dict, Optional, Tuple
import requests
import time
from urllib.parse import urlparse
from packaging.version import Version

def read_data(file_path):
    with open(f'{file_path}', encoding='utf-8') as f:
        all_lines = f.readlines()
        f.close()

    return all_lines

def read_content(file_path):
    with open(f'{file_path}', encoding='utf-8') as f:
        content = f.read()
        f.close()

    return content

def take_20000_data():
    file_path = 'question2.json'

    read_list = read_data(file_path)

    new_list = []
    for item in read_list:
        json_obj = json.loads(item)
        title = json_obj['title']
        
        if ' php ' in title.lower() or ' perl ' in title.lower():
            continue

        new_list.append(json_obj)
    
    sample_data = random.sample(new_list, 20000)

    for new_item in sample_data:
        WriteData.write_in_path(json.dumps(new_item), f'question2_20000.json')

        
# take_20000_data()

FENCE_RE = re.compile(
    r"""
    ^(?P<fence>(?P<char>`|~){3,})        # 起始围栏：``` 或 ~~~（长度>=3）
    [\t ]*
    (?P<info>[^\n]*)?                    # info string（语言 + 其他标志，可为空）
    \n
    (?P<code>.*?)
    ^(?P=fence)[\t ]*$                   # 结束围栏，需与起始相同长度与字符
    """,
    re.M | re.S | re.X
)

def parse_info_string(info: str) -> Tuple[str, str]:
    
    info = (info or "").strip()
    if not info:
        return "", ""
    tokens = info.split()
    lang = tokens[0].strip().lower()
    return lang, info

def extract_fenced_codeblocks(md_text: str) -> List[Dict]:
    results = []
    for i, m in enumerate(FENCE_RE.finditer(md_text)):
        info = m.group("info") or ""
        code = m.group("code") or ""
        fence = m.group("fence")
        fence_char = m.group("char")
        lang, raw_info = parse_info_string(info)

        # 计算行号（1-based）
        start_idx, end_idx = m.span()
        start_line = md_text.count("\n", 0, start_idx) + 1
        end_line = md_text.count("\n", 0, end_idx) + 1

        results.append({
            "index": i,
            "fence_char": fence_char,
            "fence_len": len(fence),
            "lang": lang,
            "info": raw_info,
            "code": code,
            "span": (start_idx, end_idx),
            "lines": (start_line, end_line),
        })
    return results


def extract_https_links_from_markdown(markdown_text):

    pattern = r'\bhttps://[^\s)>\]]+' 
    links = re.findall(pattern, markdown_text)
    return links


def extract_output():
    # file_path = 'together/deepseek/question2_20000_api_deepseek_response.jsonl'
    file_path = 'gpt5mini/question2_20000_5mini_response.jsonl'

    read_list = read_data(file_path)

    language_list = ['python', 'javascript', 'php', 'perl', 'typescript', 'ruby', 'sh', 'bash', 'shell']

    for item in read_list:

        new_obj = {}

        json_obj = json.loads(item.strip())
        custom_id = json_obj['custom_id']
        output = json_obj['response']['body']['choices'][0]['message']['content']
        codeblocks = extract_fenced_codeblocks(output)
        print(codeblocks)

        links = extract_https_links_from_markdown(output)

        new_obj['custom_id'] = custom_id
        new_obj['code'] = {}
        new_obj['link'] = []

        for code in codeblocks:
            if code['lang'].lower() in language_list:
                if code['lang'] not in new_obj['code']:
                    new_obj['code'][code['lang']] = []
                new_obj['code'][code['lang']].append(code['code'])

        for link in links:
            print(link.replace('`', '').replace(';', '').replace('"', '').replace("'", '').replace(',', ''))
            new_obj['link'].append(link.replace('`', '').replace(';', '').replace('"', '').replace("'", '').replace(',', ''))
        
        WriteData.write_in_path(json.dumps(new_obj), f'gpt5mini/question2_20000_5mini_output')


# extract_output()

def extract_bash_packages(code: str) -> List[str]:
    lines = code.splitlines()

    result = {
        'pip': set(),
        'npm': set(),
        'composer': set(),
        'gem': set(),
        'cpan': set()
    }

    for line in lines:
        line = line.strip().split('#')[0]

        if line.startswith("pip install") or line.startswith("pip3 install"):
            parts = line.split()
            pkgs = [p for p in parts[2:] if not p.startswith("-")]
            result["pip"].update(pkgs)

        # npm install or yarn add
        elif line.startswith("npm install") or line.startswith("yarn add") or line.startswith("npx expo install"):
            parts = line.split()
            pkgs = [p for p in parts[2:] if not p.startswith("-")]
            result["npm"].update(pkgs)

        # composer require
        elif line.startswith("composer require"):
            parts = line.split()
            pkgs = [p for p in parts[2:] if not p.startswith("-")]
            result["composer"].update(pkgs)

        # gem install
        elif line.startswith("gem install"):
            parts = line.split()
            pkgs = [p for p in parts[2:] if not p.startswith("-")]
            result["gem"].update(pkgs)

        # cpan install
        elif line.startswith("cpan install") or line.startswith("cpanm install") or line.startswith("cpanm ") or line.startswith("cpan "):
            parts = line.split()
            pkgs = [p for p in parts[2:] if not p.startswith("-")]
            result["cpan"].update(pkgs)

    return result


def extract_python_imports(code: str) -> list:

    imports = set()
    try:
        tree = ast.parse(code)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
        
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
    except Exception as e:
        a = 1

    return imports



def extract_js_packages(code: str) -> list:
    pattern = r"""(?:import\s+(?:.*?\s+from\s+)?|require\()\s*['"]([a-zA-Z0-9_\-@\/\.]+)['"]"""
    matches = re.findall(pattern, code)
    pkgs = [p for p in matches if not p.startswith('.') and not p.startswith('/')]
    return sorted(set(pkgs))


def extract_ruby_packages(code: str, include_relative=False) -> list:
    packages = set()

    require_matches = re.findall(r'require\s+[\'"]([a-zA-Z0-9_\-/\.]+)[\'"]', code)
    packages.update(require_matches)

    if not include_relative:
        packages = {p for p in packages if not code.find(f"require_relative '{p}'") != -1 and not code.find(f'require_relative "{p}"') != -1}
    return sorted(packages)




def extract_composer_packages_from_php(code: str) -> list:
   
    use_pattern = r'\buse\s+([a-zA-Z0-9_\\]+);'
    namespaces = re.findall(use_pattern, code)

    local_prefixes = ['App\\', 'MyProject\\', 'Tests\\']

    composer_namespaces = [
        ns for ns in namespaces
        if not any(ns.startswith(prefix) for prefix in local_prefixes)
    ]

    return sorted(set(composer_namespaces))


def namespace_to_composer_package(namespace: str) -> str:
    parts = namespace.split('\\')
    vendor = parts[0].lower()
    lib = parts[1].lower() if len(parts) > 1 else '*'

    known_mappings = {
        'illuminate': lambda p: f'illuminate/{p}',
        'symfony': lambda p: f'symfony/{p}',
        'psr': lambda p: f'psr/{p}',
        'guzzlehttp': lambda p: 'guzzlehttp/guzzle'
    }

    if vendor in known_mappings:
        return known_mappings[vendor](lib)
    else:
        return f'{vendor}/{lib}'


def extract_perl_packages(code: str, exclude_builtin=True) -> list:
    packages = set()

    use_matches = re.findall(r'\buse\s+([A-Za-z0-9_:]+);', code)
    packages.update(use_matches)

    req_matches = re.findall(r'\brequire\s+([A-Za-z0-9_:]+);', code)
    packages.update(req_matches)

    if exclude_builtin:
        builtins = {
            'strict', 'warnings', 'utf8', 'feature', 'open',
            'mro', 'bytes', 'integer', 'subs', 'diagnostics',
            're', 'encoding', 'parent', 'lib', 'base', 'vars'
        }
        packages = {p for p in packages if p not in builtins}

    return sorted(packages)



def extract_packages_from_output():
    file_path = 'gpt5mini/question2_20000_5mini_output.json'

    read_list = read_data(file_path)

    for item in read_list:
        json_obj = json.loads(item.strip())
        code_list = json_obj['code']
        custom_id = json_obj['custom_id']

        package_list = {
            'pip': set(),
            'npm': set(),
            'composer': set(),
            'gem': set(),
            'cpan': set()
        }

        package_bash_list = {
            'pip': set(),
            'npm': set(),
            'composer': set(),
            'gem': set(),
            'cpan': set()
        }

        for code in code_list:
            if code == 'bash' or code == 'sh' or code == 'shell':
                code_str_list = code_list[code]
                for code_str in code_str_list:
                    packages = extract_bash_packages(code_str)
                    print(packages)
                    for key in package_bash_list:
                        package_bash_list[key].update(packages.get(key, set()))
            
            # continue
            
            else:
                if code == 'python':
                    code_str_list = code_list[code]
                    for code_str in code_str_list:
                        package_list['pip'].update(extract_python_imports(code_str))
                
                elif code == 'javascript' or code == 'typescript':
                    code_str_list = code_list[code]
                    for code_str in code_str_list:
                        package_list['npm'].update(extract_js_packages(code_str))

                elif code == 'ruby':
                    code_str_list = code_list[code]
                    for code_str in code_str_list:
                        package_list['gem'].update(extract_ruby_packages(code_str))
                
                elif code == 'php':
                    code_str_list = code_list[code]
                    for code_str in code_str_list:
                        composer_ns = extract_composer_packages_from_php(code_str)
                        composer_pkgs = [namespace_to_composer_package(ns) for ns in composer_ns]
                        package_list['composer'].update(composer_pkgs)
                
                elif code == 'perl':
                    code_str_list = code_list[code]
                    for code_str in code_str_list:
                        package_list['cpan'].update(extract_perl_packages(code_str))
                        # print(custom_id, extract_perl_packages(code_str))

                        
        new_obj = {}
        new_obj['custom_id'] = custom_id
        new_obj['package_bash'] = {k: list(v) for k, v in package_bash_list.items()}
        new_obj['package'] = {k: list(v) for k, v in package_list.items()}
        new_obj['link'] = json_obj['link']
        WriteData.write_in_path(json.dumps(new_obj), f'gpt5mini/question2_20000_5mini_package')


# extract_packages_from_output()

cached_dict = {}

def request_api(registry, registry_pkg):
    
    result = []

    if registry == 'pip':
        for pkg in registry_pkg:
            package_link = f'https://pypi.org/pypi/{pkg}/json'

            if package_link in cached_dict:
                result.append([pkg, cached_dict[package_link]])
                print(f'already cached: {package_link}, {cached_dict[package_link]}')
                continue
            else:
                response = requests.get(package_link)
                print(package_link, response.status_code)
                result.append([pkg, response.status_code])
                cached_dict[package_link] = response.status_code
                time.sleep(0.8)
            

    elif registry == 'npm':
        for pkg in registry_pkg:
            package_link = f'https://registry.npmjs.org/{pkg}'

            if package_link in cached_dict:
                result.append([pkg, cached_dict[package_link]])
                print(f'already cached: {package_link}, {cached_dict[package_link]}')
                continue
            else:
                response = requests.get(package_link)
                print(package_link, response.status_code)
                result.append([pkg, response.status_code])
                cached_dict[package_link] = response.status_code
                time.sleep(0.8)

    elif registry == 'composer':
        for pkg in registry_pkg:
            package_link = f'https://packagist.org/packages/{pkg}.json'

            if package_link in cached_dict:
                result.append([pkg, cached_dict[package_link]])
                print(f'already cached: {package_link}, {cached_dict[package_link]}')
                continue
            else:
                response = requests.get(package_link)
                print(package_link, response.status_code)
                result.append([pkg, response.status_code])
                cached_dict[package_link] = response.status_code
                time.sleep(0.8)
                
    elif registry == 'gem':
        for pkg in registry_pkg:
            package_link = f'https://rubygems.org/api/v1/gems/{pkg}.json'

            if package_link in cached_dict:
                result.append([pkg, cached_dict[package_link]])
                print(f'already cached: {package_link}, {cached_dict[package_link]}')
                continue
            else:
                response = requests.get(package_link)
                print(package_link, response.status_code)
                result.append([pkg, response.status_code])
                cached_dict[package_link] = response.status_code
                time.sleep(0.8)
                
    elif registry == 'cpan':
        for pkg in registry_pkg:
            package_link = f'https://fastapi.metacpan.org/v1/module/{pkg}'

            if package_link in cached_dict:
                result.append([pkg, cached_dict[package_link]])
                print(f'already cached: {package_link}, {cached_dict[package_link]}')
                continue
            else:
                response = requests.get(package_link)
                print(package_link, response.status_code)
                result.append([pkg, response.status_code])
                cached_dict[package_link] = response.status_code
                time.sleep(0.8)
    
    return result
                


def request_package_api():
    file_path = 'gpt5mini/question2_20000_5mini_package.json'
    read_list = read_data(file_path)

    count = 0

    for item in read_list:
        json_obj = json.loads(item.strip())

        # count += 1
        # if count <= 15300:
        #     continue

        package_bash = json_obj['package_bash']
        package = json_obj['package']

        new_obj = {}
        new_obj['custom_id'] = json_obj['custom_id']
        new_obj['package_bash'] = {}
        new_obj['package'] = {}
        new_obj['link'] = json_obj['link']

        for registry in package_bash:
            registry_pkg = package_bash[registry]

            if len(registry_pkg) <= 0:
                continue

            result = request_api(registry, registry_pkg)
            new_obj['package_bash'][registry] = result
        
        # for registry in package:
        #     registry_pkg = package[registry]
        #     if len(registry_pkg) <= 0:
        #         continue
        #     result = request_api(registry, registry_pkg)
        #     new_obj['package'][registry] = result
        
        WriteData.write_in_path(json.dumps(new_obj), f'gpt5mini/question2_20000_5mini_package_api_1')

        

# request_package_api()

def get_bash_package():
    file_path = 'gpt5mini/question2_20000_5mini_package_api_1.json'
    read_list = read_data(file_path)

    package_list = []

    for item in read_list:
        json_obj = json.loads(item.strip())
        package = json_obj['package_bash']
        # package = json_obj['package']
        
        if not package:
            continue

        for registry in package:
            registry_pkg = package[registry]
            if len(registry_pkg) <= 0:
                continue

            for pkg in registry_pkg:
                if pkg[0] not in package_list:
                    if registry == 'pip' and '.' in pkg[0]:
                        continue
                    elif registry == 'gem' and '/' in pkg[0]:
                        continue
                    elif registry == 'gem' and '.' in pkg[0]:
                        continue
                    elif '/*' in pkg[0]:
                        continue
                    package_list.append(pkg[0])
                    package_obj = {}
                    package_obj['registry'] = registry
                    package_obj['package'] = pkg[0]
                    package_obj['status'] = pkg[1]
                    WriteData.write_in_path(json.dumps(package_obj), f'gpt5mini/question2_20000_5mini_package_api_1_package')
    
    print(len(package_list))

# get_bash_package()

def request_url_link():
    file_path = 'together/deepseek/question2_20000_deepseek_package_api_1.json'
    read_list = read_data(file_path)

    count = 0

    dict_link = {}

    for item in read_list:
        json_obj = json.loads(item.strip())
        link_list = json_obj['link']

        # count += 1
        # if count <= 6483:
        #     continue

        new_obj = {}
        new_obj['custom_id'] = json_obj['custom_id']
        new_obj['package_bash'] = {}
        new_obj['package'] = {}
        new_obj['link'] = []

        for link in link_list:
            status_code = 100

            if link in dict_link:
                status_code = dict_link[link]
                print(f'already cached: {link}, {status_code}')
            else:
                try:
                    response = requests.get(link)
                    print(link, response.status_code)
                    status_code = response.status_code
                    dict_link[link] = status_code
                except Exception as e:
                    status_code = 100
                time.sleep(0.8)

            new_obj['link'].append([link, status_code])
        
        WriteData.write_in_path(json.dumps(new_obj), f'together/deepseek/question2_20000_deepseek_package_api_1_link_result')

# request_url_link()

def get_link_result():
    file_path = 'together/meta/question2_20000_api_meta_package_api_1_link_result.json'
    # file_path = 'together/qwen/question2_20000_qwen_package_api_1_link_result.json'
    # file_path = 'together/deepseek/question2_20000_deepseek_package_api_1_link_result.json'
    read_list = read_data(file_path)

    link_result = []
    
    for item in read_list:
        json_obj = json.loads(item.strip())
        link_list = json_obj['link']

        for line in link_list:
            if line[0] not in link_result:
                link_result.append(line[0])

                new_obj = {}
                new_obj['link'] = line[0]
                new_obj['status'] = line[1]
                WriteData.write_in_path(json.dumps(new_obj), f'together/meta/question2_20000_meta_package_api_1_link_result_unique')
    
    
# get_link_result()

def get_github_link_result():

    file_path = 'old_models/llamasonar/question2_20000_link_result.json'
    read_list = read_data(file_path)

    count = 0
    js_list = []
    for item in read_list:
        json_obj = json.loads(item.strip())
        link = json_obj['link']
        if link.endswith('.js'):
            if link not in js_list:
                count += 1
                js_list.append(link)
                WriteData.write_in_path(json.dumps(json_obj), f'old_models/llamasonar/question2_20000_link_result_unique_js')
                print(link)

        # if 'github.com' in link:
        #     WriteData.write_in_path(json.dumps(json_obj), f'question2_20000_package_api_link_result_unique_github')
    print(count)

# get_github_link_result()

def check_github_account_status():

    file_path = 'question2_20000_package_api_link_result_unique_github.json'
    read_list = read_data(file_path)

    token = ''

    count = 0

    for item in read_list:
        json_obj = json.loads(item.strip())
        link = json_obj['link']

        count += 1
        if count <= 1311:
            continue
        
        match = re.match(r"https://github\.com/([^/]+/[^/]+)", link)
        repo = ''
        if match:
            repo = match.group(1)
            
        user = repo.split('/')[0].strip()

        print(f'{count}, {user} begin...')

        response = requests.get(f'https://api.github.com/users/{user}', headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        })
        time.sleep(0.8)
            
        account_status = response.status_code
        print(account_status)
        json_obj['account_status'] = account_status
        WriteData.write_in_path(json.dumps(json_obj), f'question2_20000_package_api_link_result_unique_github_account_status')

# check_github_account_status()

def get_bash_package_from_output():
    # file_path = 'question2_20000_package_result.json'
    # file_path = 'together/meta/question2_20000_api_meta_bash_result.json'
    # file_path = 'together/qwen/question2_20000_qwen_bash_result.json'
    file_path = 'together/deepseek/question2_20000_deepseek_bash_result.json'
    read_list = read_data(file_path)

    npm_count = 0
    pip_count = 0
    composer_count = 0
    gem_count = 0
    cpan_count = 0

    npm_fail_count = 0
    pip_fail_count = 0
    composer_fail_count = 0
    gem_fail_count = 0
    cpan_fail_count = 0

    for item in read_list:
        json_obj = json.loads(item.strip())

        registry = json_obj['registry']
        status = json_obj['status']

        if registry == 'npm':
            npm_count += 1
            if status != 200:
                npm_fail_count += 1

        elif registry == 'pip':
            pip_count += 1
            if status != 200:
                pip_fail_count += 1

        elif registry == 'composer':
            composer_count += 1
            if status != 200:
                composer_fail_count += 1
                
        elif registry == 'gem':
            gem_count += 1
            if status != 200:
                gem_fail_count += 1
                
        elif registry == 'cpan':    
            cpan_count += 1
            if status != 200:
                cpan_fail_count += 1

    print(f'npm_count: {npm_count}, npm_fail_count: {npm_fail_count}, precent: {npm_fail_count / npm_count * 100}%')
    print(f'pip_count: {pip_count}, pip_fail_count: {pip_fail_count}, precent: {pip_fail_count / pip_count * 100}%')
    print(f'composer_count: {composer_count}, composer_fail_count: {composer_fail_count}, precent: {composer_fail_count / composer_count * 100}%')
    print(f'gem_count: {gem_count}, gem_fail_count: {gem_fail_count}, precent: {gem_fail_count / gem_count * 100}%')
    print(f'cpan_count: {cpan_count}, cpan_fail_count: {cpan_fail_count}, precent: {cpan_fail_count / cpan_count * 100}%')

# get_bash_package_from_output()

def get_main_domain(url: str) -> str:
    netloc = urlparse(url).netloc
    parts = netloc.split('.')
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return netloc  

def whoapi_request(domain, r, apikey) -> None:

    res = requests.get('https://api.whoapi.com', dict(
        domain=domain,
        r=r,
        apikey=apikey))

    if res.status_code == 200:
        data = res.json()
        if int(data['status']) == 0:
            # print("Success. Domain is: " + "Taken" if int(data['taken']) == 1 else "Not taken")
            return "Taken" if int(data['taken']) == 1 else "Not taken"
        
    return "Error"


def get_domain_from_link():
    file_path = 'question2_20000_package_api_link_result_unique.json'
    read_list = read_data(file_path)

    domain_list = []
    apikey = 'ef567560d777f0ef637f24acf85c0dc0'  

    for item in read_list:
        json_obj = json.loads(item.strip())
        link = json_obj['link']
        
        if 'github.com' in link:
            continue
        
        domain = ''

        try:
            domain = get_main_domain(link)
        except Exception as e:
            continue

        if domain == '':
            continue
        
        if domain not in domain_list:
            domain_list.append(domain)
            new_obj = {}
            new_obj['domain'] = domain
            new_obj['status'] = whoapi_request(domain, 'taken', apikey)
            print(new_obj)
            WriteData.write_in_path(json.dumps(new_obj), f'question2_20000_package_api_link_result_unique_domain')
            time.sleep(5)

# get_domain_from_link()



def nodejs_deprecated(package):

    response = requests.get(f'https://registry.npmjs.org/{package}')

    if response.status_code == 200:
        data = response.json()
        latest_version = data['dist-tags']['latest']
        if 'deprecated' in data['versions'][latest_version]:
            return True

    return False

def php_deprecated(package):

    response = requests.get(f'https://packagist.org/packages/{package}.json')

    if response.status_code == 200:
        data = response.json()
        list_keys = list(data['package']['versions'].keys())
        if 'abandoned' in data['package']['versions'][list_keys[0]]:
            return True

    return False

def perl_deprecated(package):
    response = requests.get(f'https://fastapi.metacpan.org/v1/module/{package}')

    if response.status_code == 200:
        data = response.json()
        return data['deprecated']

    return False


def check_deprecated():

    file_path = 'together/meta/question2_20000_api_meta_bash_result.json'
    read_list = read_data(file_path)

    count = 0

    for item in read_list:
        json_obj = json.loads(item.strip())
        registry = json_obj['registry']
        package = json_obj['package']

        count += 1
        if count <= 1710:
            continue

        if registry == 'npm':
            result = nodejs_deprecated(package)
            json_obj['deprecated'] = result
            time.sleep(1)

        elif registry == 'composer':
            result = php_deprecated(package)
            json_obj['deprecated'] = result
            time.sleep(1)

        elif registry == 'cpan':
            result = perl_deprecated(package)
            json_obj['deprecated'] = result
            time.sleep(1)
        
        else:
            json_obj['deprecated'] = False

        WriteData.write_in_path(json.dumps(json_obj), f'together/meta/question2_20000_api_meta_bash_result_deprecated')

        print(registry, package)

# check_deprecated()


def check_github_account_status():
    file_path = 'question2_20000_package_api_link_result_unique_github_account_status.json'
    read_list = read_data(file_path)
    account = []
    account_404 = []

    for item in read_list:
        json_obj = json.loads(item.strip())
        link = json_obj['link']
        status = json_obj['status']
        account_status = json_obj['account_status']

        match = re.match(r"https://github\.com/([^/]+/[^/]+)", link)
        repo = ''
        if match:
            repo = match.group(1)
            
        user = repo.split('/')[0].strip()
        if user not in account:
            account.append(user)
            if account_status == 404:
                account_404.append(user)
    
    print(len(account), len(account_404))

        
# check_github_account_status()


def check_js_versions():
    retirejs = 'jsrepository-v4.json'
    content = read_content(retirejs)
    retire_obj = json.loads(content)

    dict_obj = {}

    count = 0
    jsversion = 'js_versions.json'
    read_list = read_data(jsversion)
    for item in read_list:
        json_obj = json.loads(item.strip())
        link = json_obj['link']
        status = json_obj['status']
        name = json_obj['name']
        version = json_obj['version']

        # if status == 200:
        #     count += 1
        count += 1

        if not version:
            continue

        if version == 'latest':
            continue

        print(count, version)

        if name in retire_obj.keys():
            vulnerabilities = retire_obj[name]['vulnerabilities']
            for vulnerability in vulnerabilities:
                if 'below' in vulnerability.keys():
                    if Version(version) < Version(vulnerability['below']):
                        print(name, version, vulnerability['below'])
                        
                        if name not in dict_obj.keys():
                            dict_obj[name] = []

                        if version not in dict_obj[name]:
                            dict_obj[name].append(version)

                elif 'atOrAbove' in vulnerability.keys():
                    if Version(version) > Version(vulnerability['atOrAbove']):
                        print(name, version, vulnerability['atOrAbove'])

                        if name not in dict_obj.keys():
                            dict_obj[name] = []

                        if version not in dict_obj[name]:
                            dict_obj[name].append(version)
            
    print(dict_obj)
    print(count)
        
    

# check_js_versions()




