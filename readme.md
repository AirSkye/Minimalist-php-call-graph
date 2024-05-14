# Minimalist PHP Call Graph

## 项目介绍

该项目从[USENIX Security 2023](https://www.usenix.org/conference/usenixsecurity23/presentation/jahanshahi)会议中提取并封装了PHP调用图生成部分的核心代码。其主要功能是生成PHP项目的函数和方法调用图，以便开发者和安全研究人员分析代码调用关系。

## 目录结构

项目的主要目录和文件结构如下：

```
Minimalist-php-call-graph
├── get_cg.py
└── call-graph/
    ├── call-graph.exe
    ├── go.mod
    ├── go.sum
    ├── main.go
    ├── packages.zip
    └── php-cg/
        ├── Gopkg.lock
        ├── Gopkg.toml
        ├── db/
        │   └── db.go
        └── scan-project/
            ├── csa_visitor/
            │   └── phpmyadmin/
            │       └── 4.0/
            │           ├── dumper.go
            │           └── namespace_resolver.go
            ├── logger/
            │   └── logger.go
            └── visitor/
                ├── Util.go
                ├── const_walker.go
                ├── def_walker.go
                ├── dumper.go
                ├── include_walker.go
                ├── namespace_resolver.go
                ├── track_walker.go
                ├── var_walker.go
                └── include_string/
                    └── include_string.go
```

## 文件说明

- **get_cg.py**: 处理PHP源码文件路径并调用`call-graph.exe`生成调用信息的脚本，进一步处理调用关系并生成JSON格式的调用图。
- **call-graph/**: 包含使用Go语言实现的PHP调用图生成代码和相关依赖。

## 使用方法

### 安装依赖

已编译了Windows环境下的exe，其他环境请自行编译。

`pip3 install tqdm regex`

### call-graph

`call-graph`目录下的`call-graph.exe`是核心工具，负责生成PHP项目的调用信息。其运行后会生成以下文件：

- `calls.txt`：包含每个方法的调用信息。
- `xxx.db`：项目的数据库文件。
- `functions.txt`：项目中所有函数的列表。
- `methods.txt`：项目中所有方法的列表。
- `unresolved.txt`：未解析的调用信息。

#### 文件内容说明

示例源代码如下

```php
if (!defined('BASEPATH')) exit('No direct script access allowed');
class Admin extends CI_Model
{
    function __construct (){
        parent:: __construct ();
        //判断IP白名单
        if(Admin_Ip != ''){
            $ip = getip();
            $iparr = explode('|', Admin_Ip);
            if(!in_array($ip, $iparr)){
                show_404();
            }
        }
    }
	
    //判断后台是否登入
    function login($sid=0,$key=''){
        if(empty($key)){
            $id = !$this->cookie->get('admin_id') ? 0 : $this->cookie->get('admin_id');
            $login =  !$this->cookie->get('admin_login') ? '' :  $this->cookie->get('admin_login');
        }else{
            $str  = sys_auth($key,1);
            $id   = isset($str['id'])?intval($str['id']) : 0;
            $login = isset($str['login'])?$str['login'] : '';
        }
        $islog = false;
        if(!empty($id) && !empty($login)){
            $admin = $this->mcdb->get_row('admin','name,pass',array('id'=>$id));
            if($admin && md5($id.$admin->name.$admin->pass.Admin_Code) == $login){
                $islog = true;
            }
        }
        if($sid > 0){
            return $islog;
        }else{
            //未登录
            if(!$islog){
                $this->cookie->set('admin_id');
                $this->cookie->set('admin_nichen');
                $this->cookie->set('admin_login');
                //判断直接打开还是ajax
                if(strpos($_SERVER['HTTP_ACCEPT'],'application/json') === false){
                    die("<script language='javascript'>top.location='".links('login')."';</script>");
                }else{
                    get_json('您已登陆超时!!!');
                }
            }
        } 
    }
}
```

生成文件如下

- **calls.txt**: 包含每个方法的调用信息，如下示例：

  ```
  Admin\__construct|D:\xxx\Admin.php->#(CI_Model)\__construct#0#getip#0#explode#2#in_array#2#show_404#0
  Admin\login|D:\xxx\Admin.php->#(.*)\(get)#1#(.*)\(get)#1#(.*)\(get)#1#(.*)\(get)#1#sys_auth#2#intval#1#(.*)\(get_row)#3#md5#1#(.*)\(set)#1#(.*)\(set)#1#(.*)\(set)#1#strpos#2#links#1#get_json#1
  main|D:\xxx\Admin.php->#defined#1
  ```

  分隔符`|`前表示当前方法/函数信息，分隔符后表示方法/函数文件路径，`->`后表示当前方法/函数中调用的方法/函数，`(CI_Model)\__construct`中`CI_Model` 表示对象名，`__construct`表示对象方法，不带`\`的就为函数调用。

- **xxx.db**: 项目的数据库文件，包含项目的元数据。

- **functions.txt**: 项目中所有函数的列表和路径，每行一个函数名。

- **methods.txt**: 项目中所有方法的列表和路径，每行一个方法名。

- **unresolved.txt**: 未解析的调用信息，格式为`{文件路径}{函数或方法名}`。

### 运行 `get_cg.py`

在根目录下，运行`get_cg.py`脚本，该脚本会处理PHP源码文件路径，并调用`call-graph.exe`生成调用信息，然后进一步处理这些信息，生成最终的调用关系图并输出到output中指定的项目文件夹内JSON格式文件。

示例命令：

```
python get_cg.py -d /path/to/php/project
```

### 帮助信息

```
Usage: get_cg.py -d <source_dir> -p <output_path> -o <output_file> -e <exclude_list> -i <include_list>
------------------------------------------------------------------------------------------------------
Options:
    -h  : 显示帮助信息
    -d  : 指定PHP源码项目目录（必须指定）
    -p  : 指定输出路径，默认为'output/'
    -o  : 指定输出JSON文件名，默认为'output.json'，输出到output中指定的项目目录
    -e  : 排除源码中某些文件夹，格式为逗号分隔的文件夹列表，例如'folder1,folder2'
    -i  : 只包含源码中某些文件夹，格式为逗号分隔的文件夹列表，如果指定，只处理这些文件夹内的文件
```

### 查看输出

生成的`output.json`文件将包含详细的调用关系信息，结构如下：

```json
{
    "Admin\\__construct|D:\\xxx\\apps\\models\\Admin.php": {
        "native": [
            "explode",
            "in_array"
        ],
        "(CI_Model)\\__construct": [
            "CI_Model\\__construct|D:\\xxx\\system\\core\\Model.php"
        ],
        "getip": [
            "getip|D:\\xxx\\apps\\helpers\\common_helper.php"
        ],
        "show_404": [
            "show_404|D:\\phpStudy1\\PHPTutorial\\WWW\\mccms\\tainttest\\Common.php",
            "show_404|D:\\xxx\\system\\core\\Common.php"
        ]
    },
    "Admin\\login|D:\\xxx\\apps\\models\\Admin.php": {
        "native": [
            "md5",
            "intval",
            "strpos"
        ],
        "links": [
            "links|D:\\xxx\\apps\\helpers\\link_helper.php"
        ],
        "(.*)\\(get_row)": [
            "Mcdb\\get_row|D:\\xxx\\apps\\models\\Mcdb.php"
        ],
        "get_json": [
            "get_json|D:\\xxx\\apps\\helpers\\common_helper.php"
        ],
        "(.*)\\(get)": [
            "CI_Cache\\get|D:\\Cache.php",
            "CI_Cache_wincache\\get|D:\\Cache_wincache.php"
        ],
        "sys_auth": [
            "sys_auth|D:\\xxx\\apps\\helpers\\common_helper.php"
        ],
        "(.*)\\(set)": [
            "Cookie\\set|D:\\xxx\\apps\\libraries\\Cookie.php",
            "qrstr\\set|D:\\xxx\\class\\phpqrcode\\phpqrcode.php",
            "Composer\\Autoload\\ClassLoader\\set|D:\\xxx\\class\\up_yun\\vendor\\composer\\ClassLoader.php",
            "CI_DB_query_builder\\set|D:\\xxx\\system\\database\\DB_query_builder.php"
        ]
    }
}
```

其中，键名如`Admin\\__construct|D:\\xxx\\apps\\models\\Admin.php`表示Admin类的构造方法，键`native`的值表示其中调用的PHP原生方法，其余键表示调用的其他方法或函数，其中的`(.*)`表示可能存在多个对象调用此方法，其余键值表示其的文件路径，对应具体的对象和方法（可能多个）。

## 注意事项

- 确保路径配置正确，尤其是PHP源码目录和输出目录。
- `get_cg.py`脚本依赖于`call-graph.exe`的运行结果，请先确保`call-graph.exe`正常运行并生成必要的文件。