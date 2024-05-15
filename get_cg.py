import sys, os
import re, regex
import json
import logging
import getopt
import subprocess
import shutil
from tqdm import tqdm

IMPROVE_CANDID_SELECTION = False

def load_files(path):
    ## read function files
    f = open(path + "functions.txt", "r").readlines()
    funcs = set()
    i = 0
    for line in f:
        funcs.add(line.strip("\n"))

    max_func = len(funcs)
    ## read method files
    m = open(path + "methods.txt", "r").readlines()
    methods = set()
    for line in m:
        methods.add(line.strip("\n"))

    max_method = len(methods)

    unres = open(path + "unresolved.txt", "r").readlines()
    unres_funcs = set()
    for line in unres:
        x = re.search("{(.*)}{(.*)}", line.strip("\n"))
        if x.group(1) and x.group(2):
            unres_funcs.add((x.group(1), x.group(2)))
    ## read calls file which include all the calls in the web app
    return (methods, funcs, max_method, max_func, unres_funcs)


## extract a set of items from List that are similar to Item
def getMatchFuncs(lst, Item):
    l = []
    if Item.startswith('|'):
        Item = Item[1:]
    Item = Item.replace("\\", "\\\\")
    Item = Item + "\|"
    try:
        r = regex.compile(Item, re.IGNORECASE)
        l = list(filter(r.match, lst))
    except Exception as e:
        logging.warning("getMatchFuncs[%s]:Item is [%s]" % (e, Item))
    return l


def getMatchMethods(lst, item):
    l = []
    if item.startswith('|'):
        item = item[1:]
    item = item.replace("\\", "\\\\")
    item = item + "\|"
    try:
        r = regex.compile(item, re.IGNORECASE)
        l = list(filter(r.match, lst))
        ## check for replacement of __construct with the classname
        if "__construct" in item and len(l) == 0:
            clsName = item.split("\\")[0]
            res = [x for x in lst if x.startswith(clsName + "\\" + clsName)]
            return res
    except Exception as e:
        logging.warning("getMatchMethods[%s]: Item is [%s]" % (e, item))
    return l


data = {}


def gen_cg(methods, funcs, path, exclude_folders, include_folders):
    # 从文本文件读取调用图数据
    cg_file = open(path + "calls.txt", 'r').readlines()

    # 使用正则表达式替换每行内容中的 `#\d#`
    pattern = re.compile(r'#\d#|#\d')
    cg_file = [pattern.sub('#', line) for line in cg_file]
    # 初始化字典来存储调用图和反向调用图
    cg = {}
    cg_rev = {}

    # 遍历调用图文件的每一行，并显示进度
    for line in tqdm(cg_file, desc="Processing call-graph file"):
        # 从行中提取调用者函数/方法
        caller = line.strip("\n").split("->")[0]
        # 获取函数文件路径
        file_path = caller.split('|')[1] if '|' in caller else ""
        folder_path = os.path.dirname(file_path)
        # 判断是否跳过或者只处理某些目录
        if any(exclude in folder_path for exclude in exclude_folders):
            continue
        if include_folders and not any(include in folder_path for include in include_folders):
            continue
        # 初始化一个集合来保存所有被调用者（被调用者是由调用者调用的函数/方法）
        callees = set()

        # 如果行中没有包含'->'，表示没有调用关系，则跳过处理
        if len(line.strip("\n").split("->")) < 2:
            continue

        # 如果行中'->'后的部分没有包含'#'，则跳过处理
        if len(line.strip("\n").split("->")[1].split("#")) < 2:
            continue

        # 初始化一个字典来保存每个被调用者被调用的次数
        hmap = {}

        # 根据预定义的标志选择是否提升候选者选择
        if IMPROVE_CANDID_SELECTION:
            # 从行中提取并处理每个被调用者及其调用次数
            tmp = line.strip("\n").split("->")[1].split("#")[1:]
            for i in range(0, len(tmp), 2):
                c = tmp[i]
                hmap[c] = int(tmp[i + 1])
                callees.add(c)
        else:
            # 仅添加被调用者，不计算它们被调用的次数
            for c in line.strip("\n").split("->")[1].split("#")[1:]:
                if c:  # 检查c是否为空
                    callees.add(c)

        # 初始化调用者在调用图中，并分别记录被调用的函数和原生函数
        cg[caller] = {"called": [], "native": []}
        data[caller] = {"native": []}

        # 遍历识别的每一个被调用者
        for callee in list(callees):
            # 初始化集合来保存匹配的函数和方法
            mList = set()
            fList = set()

            # 根据被调用者中是否含有'\\'来检查是函数还是方法
            if "\\" not in callee:
                # 匹配函数列表
                name = getMatchFuncs(funcs, callee);
                if name:
                    matched_funcs = list(name)
                    if not matched_funcs:  # 如果没有匹配到自定义函数，假设它是原生PHP函数
                        cg[caller]["native"].append(callee)
                        data[caller]["native"].append(callee)
                    fList.update(matched_funcs)
                    # logging.warning("----- 找到被调用函数 [%s]" % (callee))
                    # 获取匹配的方法并将它们添加到函数列表中
                    for f in getMatchMethods(methods, callee):
                        fList.add(f)
                else:
                    logging.warning("----- 未匹配到被调用函数 [%s]" % (callee))
            else:
                # 为方法被调用者获取匹配的方法
                name = getMatchMethods(methods, callee)
                if name:
                    mList.update(list(name))
                    # logging.warning("----- 找到被调用方法 [%s]" % (callee))
                else:
                    logging.warning("----- 未匹配到被调用方法 [%s]" % (callee))


            # 如果被调用者包含动态函数调用，则跳过处理
            if "call_user_func" in callee:
                # unhandled.add(caller)
                logging.error("调用者调用了动态函数: %s" % (caller))
                continue

            # 处理函数列表和方法列表中的条目
            for i in list(fList):
                if "Test" not in i and "simpletest" not in callee:
                    cg[caller]["called"].append(i)
                    if i not in cg_rev.keys():
                        cg_rev[i] = []
                    cg_rev[i].append(caller)
                    if callee not in data[caller]:
                        data[caller][callee] = []
                    data[caller][callee].append(i)

            for i in list(mList):
                if "Test" not in i and "simpletest" not in i:
                    cg[caller]["called"].append(i)
                    if i not in cg_rev.keys():
                        cg_rev[i] = []
                    cg_rev[i].append(caller)
                    if callee not in data[caller]:
                        data[caller][callee] = []
                    data[caller][callee].append(i)

    # 返回调用图、反向调用图和额外的数据
    return cg, cg_rev, data

def show_help():
    print('''
Usage: get_cg.py -d <source_dir> -p <output_path> -o <output_file> -e <exclude_list> -i <include_list>
------------------------------------------------------------------------------------------------------
Options:
    -h  : 显示帮助信息
    -d  : 指定PHP源码项目目录（必须指定）
    -p  : 指定输出路径，默认为'output/'
    -o  : 指定输出JSON文件名，默认为'output.json'，输出到output中指定的项目目录
    -e  : 排除源码中某些文件夹，格式为逗号分隔的文件夹列表，例如'folder1,folder2'
    -i  : 只包含源码中某些文件夹，格式为逗号分隔的文件夹列表，如果指定，只处理这些文件夹内的文件
        ''')

def main(argv):
    # 配置默认的输出和路径
    PATH =  'output/'
    json_output = "output.json"
    db_name = ""
    php_source_dir = "D:/phpStudy1/PHPTutorial/WWW/Topsrc-dev/"
    exclude_list = ['ThinkPHP','Topsec_Alpha_Lab@mysql','vendor']
    include_list = []
    # 解析命令行参数
    try:
        opts, args = getopt.getopt(argv, "hd:p:o:e:i:", ["help=", "source-dir=", "path=", "output=", "exclude=", "include="])
    except getopt.GetoptError as e:
        print("错误的参数: ", e)
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            show_help()
            sys.exit(0)
        if opt in ("-e", "--exclude"):
            exclude_list = arg.split(',')
        elif opt in ("-i", "--include"):
            include_list = arg.split(',')
        elif opt in ("-d", "--source-dir"):
            php_source_dir = arg
        elif opt in ("-p", "--path"):
            PATH = arg
        elif opt in ("-o", "--output"):
            json_output = arg
        elif opt in ("-h", "--help"):
            show_help()
    if not php_source_dir:
        print("需要指定PHP源码项目目录，-h查看帮助")
        sys.exit(2)

    # 确保路径末尾有分隔符
    php_source_dir = os.path.join(php_source_dir, '')

    # 从路径中提取数据库名（即项目名），并过滤特殊字符
    db_name = re.sub(r'[^a-zA-Z0-9]', '_', os.path.basename(os.path.normpath(php_source_dir)))
    call_graph_exe = "call-graph/call-graph.exe"
    db_path = f"{php_source_dir} {db_name}.db"
    # 确保输出目录存在
    output_dir = os.path.join(PATH, db_name)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 检查是否需要运行call-graph.exe
    required_files = ["calls.txt", f"{db_name}.db", "functions.txt", "methods.txt", "unresolved.txt"]
    files_exist = all(os.path.exists(os.path.join(output_dir, f)) for f in required_files)
    if not files_exist:
        # 调用call-graph.exe生成必要文件
        print("调用call-graph.exe生成必要文件")
        subprocess.run([call_graph_exe, php_source_dir, db_name + ".db"], check=True)

        # 移动文件到指定目录，如果存在则覆盖
        for file in required_files:
            dest_file = os.path.join(output_dir, file)
            if os.path.exists(dest_file):
                os.remove(dest_file)
            shutil.move(file, dest_file)

    # 更新路径以加载文件
    PATH = os.path.join(output_dir,'')

    # 加载必要的文件
    (methods, funcs, max_method, max_func, unres_funcs) = load_files(PATH)

    # 生成调用图
    print("生成调用图")
    cg, cg_rev, data = gen_cg(methods, funcs, PATH, exclude_list, include_list)

    # 输出调用图到JSON文件
    with open(os.path.join(output_dir, json_output), 'w') as outfile:
        json.dump(data, outfile, indent=4)
        print(f"调用图已输出到 {os.path.join(output_dir, json_output)}")

if __name__ == "__main__":
    main(sys.argv[1:])