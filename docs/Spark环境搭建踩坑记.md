# PySpark on Windows 环境搭建踩坑记

> 记录日期：2026-09-23
> 环境：Windows + Python 3.14.7 + PySpark 4.2.0 + 中文用户名（`C:\Users\瞿崇荣\`）
> 结论：**四个坑全部绕过，最终 SPARK_HOME 用目录联接指向 ASCII 路径**

---

## 起因

毕业设计需要在 1233 万条数据上做分布式处理，必须用 PySpark。
但按常规方法安装后，`SparkSession.builder.getOrCreate()` 直接报错：

```
TypeError: 'JavaPackage' object is not callable
```

排查过程与最终方案记录如下，**每一步都是实测验证过的**。

---

## 坑 1：JAVA_HOME 指向一个空目录

### 现象

```powershell
> echo $env:JAVA_HOME
D:\Java\jdk-17

> Test-Path "D:\Java\jdk-17\bin\java.exe"
False          # 目录存在，但是空的
```

**环境变量配了，Java 其实没装。** 而 PySpark 4.x 要求 Java 17+（4.x 已抛弃 Java 8）。

本机实际只有 JDK 8：`D:\jdk-8u471-windows-x64\jdk1.8.0_471`

### 解决方案：便携版 JDK

不用 `winget install`（需要管理员权限、会改系统环境），改用**解压即用的便携版**：

```powershell
# 从 Adoptium 官方 API 下载最新 JDK 17（约 182 MB）
$url = "https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jdk/hotspot/normal/eclipse"
Invoke-WebRequest -Uri $url -OutFile "F:\myprogect\.tools\jdk17.zip"
Expand-Archive "F:\myprogect\.tools\jdk17.zip" -DestinationPath "F:\myprogect\.tools\jdk17"
```

得到 `F:\myprogect\.tools\jdk17\jdk-17.0.20.1+1\`，直接用，不写注册表、不改 PATH、删掉即卸载。

---

## 坑 2：SPARK_HOME 指向旧版本，导致 Python 代码与 Spark jar 版本错配

### 现象

pip 装的是 PySpark **4.2.0**，但 Spark 启动后 `spark.version` 报 **3.5.8**。

```
pyspark.__version__ = 4.2.0
spark.version       = 3.5.8      # ← 对不上！
```

### 根因

系统级环境变量里早就设了：

```powershell
[Environment]::GetEnvironmentVariable('SPARK_HOME','Machine')
# D:\spark\spark-3.5.8-bin-hadoop3-scala2.13
```

PySpark 启动时会**优先使用 `SPARK_HOME` 里的 jar**，而不是自己 pip 包内自带的那套。
于是变成「4.2.0 的 Python 代码 + 3.5.8 的 Java 类」，中间的 `py4j` 网关解析类失败，
报 `'JavaPackage' object is not callable`。

### 诊断方法

```python
import pyspark, os
print(pyspark.__file__)                       # pip 包位置
print(os.environ.get('SPARK_HOME'))           # 看它指向哪
import glob
print(glob.glob(os.path.join(os.path.dirname(pyspark.__file__),'jars','spark-core*.jar')))
```

### 解决方案

让 `SPARK_HOME` 指向 **PySpark 自己包内的那套 jar**，版本自然一致。

---

## 坑 3（最坑）：中文路径会打断 Spark 的启动脚本

### 现象

即使把 `SPARK_HOME` 指向 pip 包目录，仍然报：

```
ClassNotFoundException: org.apache.spark.deploy.SparkSubmit
```

而手工检查过，jar 里**确实有**这个类：

```powershell
# spark-core_2.13-4.2.0.jar 内含
org/apache/spark/deploy/SparkSubmit$$anon$1.class
org/apache/spark/deploy/SparkSubmit$$anon$2.class
... （共 5854 个条目）
```

### 根因

PySpark 启动 JVM 的方式是调用批处理脚本：

```
$SPARK_HOME/bin/spark-submit.cmd
```

而 pip 把包装在：

```
C:\Users\瞿崇荣\AppData\Local\Programs\Python\Python314\Lib\site-packages\pyspark
         ^^^^^^ 中文
```

**Windows 批处理脚本处理不了路径里的非 ASCII 字符**，导致 classpath 拼装失败，
`java` 命令拿不到 jar，于是找不到主类。

### 验证方法（关键对照实验）

系统里还有一个纯 ASCII 路径的 Spark 安装：

```powershell
$env:SPARK_HOME = "D:\spark\spark-3.5.8-bin-hadoop3-scala2.13"
& "$env:SPARK_HOME\bin\spark-submit.cmd" --version
```

**立刻成功**，打印出 Spark 的 ASCII art 和版本号。

→ 对照实验证明：**问题不在 Java、不在 jar、不在版本，而在路径里的中文。**

### 解决方案：目录联接（Junction）

`mklink /J` 创建目录联接，**不需要管理员权限**，也**不复制任何数据**：

```powershell
New-Item -ItemType Junction `
  -Path   "F:\myprogect\.tools\spark42" `
  -Target "C:\Users\瞿崇荣\AppData\Local\Programs\Python\Python314\Lib\site-packages\pyspark"
```

于是：

```
F:\myprogect\.tools\spark42   ──(联接)──>   C:\Users\瞿崇荣\...\pyspark
        ↑ 纯 ASCII                              ↑ 真实位置（含中文）
```

再把 `SPARK_HOME` 指向 ASCII 那一侧：

```powershell
$env:SPARK_HOME = "F:\myprogect\.tools\spark42"
& "$env:SPARK_HOME\bin\spark-submit.cmd" --version
# → Spark 4.2.0 ✓
```

> **为什么不用 8.3 短名？**
> 试过，没用。`瞿崇荣` 只有 3 个字符，本来就满足 8.3 命名规则，
> 系统不会为它生成短名，所以短路径里仍然是中文。

---

## 坑 4：Python worker 连不回来

### 现象

Spark 能启动了，但一执行任务就报：

```
org.apache.spark.SparkException: Python worker failed to connect back
Caused by: java.net.SocketTimeoutException: Timed out while waiting for the
           Python worker to connect back
```

### 根因

两个原因叠加：

1. **没有显式指定 Python 解释器** —— executor 启动 worker 进程时找不到该用哪个 Python
2. **driver 绑到了网卡 IP** —— 日志里能看到 `(10.87.231.41 executor driver)`，
   子进程回连这个地址时可能被 Windows 防火墙拦截

### 解决方案

```python
import os, sys
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

spark = (SparkSession.builder
         .master("local[*]")
         .config("spark.driver.host", "127.0.0.1")
         .config("spark.driver.bindAddress", "127.0.0.1")
         .getOrCreate())
```

---

## 最终可用配置

```python
import os, sys, glob, subprocess

# 1. JDK 17（便携版，不需要管理员权限）
java_home = r"F:\myprogect\.tools\jdk17\jdk-17.0.20.1+1"
os.environ["JAVA_HOME"] = java_home
os.environ["PATH"] = os.path.join(java_home, "bin") + os.pathsep + os.environ["PATH"]

# 2. SPARK_HOME 指向 ASCII 路径（用目录联接绕过中文路径）
os.environ["SPARK_HOME"] = r"F:\myprogect\.tools\spark42"

# 3. 显式指定 Python 解释器
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

# 4. 绑定回环地址
from pyspark.sql import SparkSession
spark = (SparkSession.builder
         .master("local[*]")
         .config("spark.driver.host", "127.0.0.1")
         .config("spark.driver.bindAddress", "127.0.0.1")
         .config("spark.sql.shuffle.partitions", "16")
         .getOrCreate())
```

**这些逻辑已经封装在 `src/step6_spark.py` 的 `setup_env()` 函数里，直接跑脚本即可。**

---

## 一句话总结每个坑

| # | 坑 | 一句话 |
|---|---|---|
| 1 | JAVA_HOME 指向空目录 | 配了环境变量 ≠ 装了软件，要验证路径下真有 `java.exe` |
| 2 | SPARK_HOME 版本错配 | PySpark 会优先用 SPARK_HOME 的 jar，版本必须和 pip 包一致 |
| 3 | **中文路径** | Windows 批处理脚本处理不了非 ASCII 路径，用 `mklink /J` 建目录联接绕过 |
| 4 | Python worker 连不回来 | 显式指定 `PYSPARK_PYTHON`，并把 driver 绑到 `127.0.0.1` |

---

## 这些能不能写进毕设？

**能，而且应该写。**

这不是"环境配置的琐事"，而是**实打实的工程问题排查能力**：

- 坑 2 用了「版本比对 + 诊断脚本」定位
- 坑 3 用了**对照实验**（换 ASCII 路径立刻成功）锁定根因 —— 这是标准的科学方法
- 坑 4 通过读异常堆栈找到「回连超时」这个关键词

**答辩时能讲清楚"我遇到什么问题、怎么定位、为什么这么解决"，比背概念有说服力得多。**
