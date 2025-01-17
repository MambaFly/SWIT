### 导入必要模块
from mpn_models.dmpnn import MPNN    # MPNN模型
from mpn_models.chemprop import *    # 化合物性质处理模块
from mpn_models import utils    # 数据处理模块
import os
import argparse
import sys
from joblib import dump
import numpy as np
import math
import scipy.stats as stats
from datetime import datetime
import matplotlib.pyplot as plt

### 获取当前时间，并构造后缀避免文件名冲突
current_time=datetime.now()
suffix=str(current_time.year)+"_"+str(current_time.month)+"_"+str(current_time.day)

### 解析命令行参数
parser = argparse.ArgumentParser(description='Train a target-specific scoring model.')
parser.add_argument('training_dataset_path', type=str, 
                    help='a path to a file in csv format. It could be absolute path or relative path. Example: ./data/ampc_round2_test1k.csv The first column should be SMILES and second column should be score.')
parser.add_argument('task_name', type=str, default="task1",
                    help='the name of the output folder located under swit/')
parser.add_argument('--testing_dataset_path', type=str, default=None,
                    help='a path to a file in csv format. It could be absolute path or relative path. Example: ./data/ampc_round2_test1k.csv The first column should be SMILES and second column should be score. default: None')
parser.add_argument('--ncpu', type=int, default=1,
                    help='number of cores to available to each worker/job/process/node. default: 1')
parser.add_argument('--epochs', type=int, default=50,
                    help='number of iterations for model training. default: 50')
args = parser.parse_args()

# 创建输出目录
if not os.path.exists("./examples/"+args.task_name+"/preds"):
    cmd="mkdir -p ./examples/"+args.task_name+"/preds"
    os.system(cmd)
current_work_dir = os.getcwd()
os.chdir(current_work_dir)

### 读取和处理训练集数据
scores_csv       = args.training_dataset_path
scores, failures = utils._read_scores(scores_csv)
xs, ys           = zip(*scores.items())
print(f"input data size:{len(xs)}")

### 构建MPNN模型并训练
my_model= MPNN(ncpu=args.ncpu,epochs=args.epochs)
my_model.train(xs, ys,args.task_name)
#print(my_model)
print("Trained model saved in /swit/examples/"+args.task_name+"...")
folder_name=sorted(os.listdir("./examples/"+args.task_name+"/lightning_logs"))[-1]
## 存储模型使用的数据归一化器
dump(my_model.scaler,f'./examples/'+args.task_name+'/lightning_logs/'+folder_name+'/std_scaler.bin',compress=True)
print("The scaler is already stored in {}".format('./examples/'+args.task_name+'/lightning_logs/'+folder_name+'/std_scaler.bin'))

### 测试模型预测性能
if not args.testing_dataset_path is None:
    ### 加载数据
    scores_csv       = args.testing_dataset_path
    scores, failures = utils._read_scores(scores_csv)
    xs, ys           = zip(*scores.items())
    print(f"input data size:{len(xs)}")
    ### 预测
    preds_chunks=my_model.predict(xs)
    pred_scores=[]
    #print(preds_chunks)
    for idx in range(len(preds_chunks)): # 对每个预测块迭代
        for pred_score in preds_chunks[idx]:
                pred_scores.append(pred_score[0])
    print(f"output data size:{len(pred_scores)}")

    ### calculate RMSE,PCC between predicted score and target score
    if len(pred_scores)==len(ys): # 检查数目是否一致
        se_lst = []
        new_pred=[]
        new_ys=[]
        writer=open("./examples/"+args.task_name+"/preds/prediction"+suffix+".csv","w")
        writer.write("prediction,target\n")
        ## 添加筛选后的目标分数、预测分数、平方误差
        for idx,target_score in enumerate(ys):
            if target_score>=0:  # 过滤掉非负的对接分数
                continue
            se = (target_score-pred_scores[idx])**2
            se_lst.append(se)
            new_pred.append(pred_scores[idx])
            new_ys.append(target_score)
            writer.write(str(round(pred_scores[idx],1))+","+str(target_score)+"\n")
        writer.close()
        ## 计算rmse、pcc
        mse = np.average(se_lst)
        rmse = math.sqrt(mse)
        PCC,p =stats.pearsonr(new_pred,new_ys)
        print(f"length of score list:{len(se_lst)}")
        print(f"RMSE:{rmse:.2f}")
        print(f"PCC :{PCC:.2f}")
        ## 绘制曲散点图
        fig=plt.figure(figsize=(15,15))
        x = np.linspace(-19,-1,19)
        y = x
        plt.scatter(pred_scores,ys,color='orange',s=6)
        plt.xlim(-20,0)
        plt.ylim(-20,0)
        plt.tick_params(labelsize=20)
        plt.plot(x, y,"b--")
        plt.xlabel("prediction",size=30)
        plt.ylabel("target",size=30)
        plt.savefig("./examples/"+args.task_name+"/preds/pred_target_scatter"+suffix+".png")
    else:
        print("Warning: the length of the prediciton and target are not the same.")
