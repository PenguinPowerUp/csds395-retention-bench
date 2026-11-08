# Comparison with Published Work

Pengjun Lu, 2026-11-08. This file compares retention-bench with published work only and uses no figure from any private project. Every number quoted from another paper was checked against that paper's full text.

# 1. Work on World of Warcraft

| Study                | Question                                                        | What it reports                                                                                                             |
| -------------------- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Tarng et al. 2008    | Whether game hours predict how long players stay; no classifier | Only 7,043 of 34,521 accounts stay active beyond 30 days; short-term play predicts short-term play, not subscription length |
| Tarng et al. 2009    | Predicts unsubscription, mainly in another MMORPG               | Detects with 80% accuracy whether WoW avatars are discarded in the near future                                              |
| Lee et al. 2011      | Describes the dataset; makes no prediction                      | 60% of users stay subscribed over a year                                                                                    |
| Siqueira et al. 2017 | Estimates which players renew their subscription next year      | Regression on level and play density, R² = 0.90                                                                             |
| Khan 2020 (arXiv)    | Predicts which players churn within six months                  | ROC-AUC for four classifiers                                                                                                |
| Humenhuk et al. 2021 | Studies how to label churn; makes no prediction                 | Mean absence before a return is 2.17 to 12.85 days                                                                          |
| Hossain et al. 2023  | Uses the past month to predict play again 30 to 60 days later   | Random forest ROC-AUC 0.978, logistic regression 0.70, with 10-fold cross-validation                                        |

These studies ask whether established players leave over months. retention-bench asks whether a character created today comes back tomorrow. Hossain et al. even exclude every player who joined less than 30 days before, which is exactly the population retention-bench studies. Yet Tarng et al. (2008) show that this population is most of the game: four in five accounts stop within 30 days. Day-one return on WoWAH is therefore a new task, and no number above is a baseline for it.

# 2. Early churn in other games

| Study                 | Question                                    | Task                                                                | Result                                                   |
| --------------------- | ------------------------------------------- | ------------------------------------------------------------------- | -------------------------------------------------------- |
| Mustač et al. 2022    | Next-day return of new players              | Uses day 1 to predict no play on day 2                              | Random forest ROC-AUC 0.77                               |
| Milošević et al. 2017 | Early churn and targeted push notifications | Uses day 1 to predict no return within 14 days of the last activity | Gradient boosting ROC-AUC 0.83, logistic regression 0.79 |
| Drachen et al. 2016   | How early retention can be predicted        | Uses day 1 to predict any play on days 8 to 14                      | LR accuracy 0.684 against 0.595 majority                 |
| Kim et al. 2017       | Churn in casual games                       | Uses days 1 to 5 to predict no play on days 6 to 15                 | ROC-AUC 0.711 to 0.824 across three games                |
| Lee et al. 2019       | Churn across a business-model change        | Uses 8 weeks of play to predict no play for over 5 weeks            | Winning F1 0.61 and 0.63                                 |

Mustač et al. use the same label as retention-bench. Their random forest reaches ROC-AUC 0.77; retention-bench reaches 0.771 with session minutes alone and 0.803 with all five features. Milošević et al. also use only first-day data, and their logistic regression reaches 0.79 on a sample balanced to half churners. The games differ, so this shows that our result is plausible, not that one method is better.

# 3. What agrees and what does not

**Playtime carries most of the signal.** This holds in other games and in retention-bench:

| Study               | Finding                                                                                                |
| ------------------- | ------------------------------------------------------------------------------------------------------ |
| Kim et al. 2017     | Active duration and play count rank first and second in all three games; two or three features suffice |
| Drachen et al. 2016 | Rounds, sessions and session duration are the most predictive features                                 |
| retention-bench     | Session minutes alone reach 2.5 times the PR-AUC floor; all five features reach 2.7                    |

**Whether a more complex model helps is not tested here.** The answer differs across studies. Kim et al. find logistic regression at most 0.017 ROC-AUC behind gradient boosting, random forests and two deep models. On first-day data, Milošević et al. find gradient boosting 0.04 ahead. On WoWAH with month-long windows, Hossain et al. find random forest far ahead, 0.978 against 0.70. However, our retention-bench trains only logistic regression, so it does not show which case holds for day-one return on WoWAH.

# 4. Limits

- **Different tasks.** The studies differ in game, unit, window, horizon and base rate. Only ROC-AUC is roughly comparable across them.
- **Sources.** Khan (2020) is an arXiv preprint and is not peer-reviewed. Tarng et al. (2008) collected their own World of Warcraft traces in 2005 to 2007 with the same method as WoWAH; they are not the WoWAH release.

# References

- Drachen et al. (2016). Rapid Prediction of Player Retention in Free-to-Play Mobile Games. *Proc. AIIDE* 12(1), 23–29. doi:10.1609/aiide.v12i1.12856
- Hossain, Azizi, Zaman (2023). Predicting Subscription Renewal Using Binary Classification in World of Warcraft. *Entertainment Computing* 44, 100522. doi:10.1016/j.entcom.2022.100522
- Humenhuk, Kummer, Paraiso (2021). Optimizing Profit by Mitigating Recurrent Churn Labeling Issues. *Proc. AIIDE* 17(1), 26–33. doi:10.1609/aiide.v17i1.18887
- Kaufman, S., Rosset, S., Perlich, C. (2011). Leakage in Data Mining: Formulation, Detection, and Avoidance. *Proc. KDD*, 556–563. doi:10.1145/2020408.2020496
- Khan (2020). Predicting Customer Churn in World of Warcraft. arXiv:2006.15735
- Kim, S., Choi, D., Lee, E., Rhee, W. (2017). Churn Prediction of Mobile and Online Casual Games Using Play Log Data. *PLOS ONE* 12(7), e0180735. doi:10.1371/journal.pone.0180735
- Lee, E., et al. (2019). Game Data Mining Competition on Churn Prediction and Survival Analysis Using Commercial Game Log Data. *IEEE Trans. Games* 11(3), 215–226. doi:10.1109/TG.2018.2888863
- Lee, Y.-T., Chen, K.-T., Cheng, Y.-M., Lei, C.-L. (2011). World of Warcraft Avatar History Dataset. *Proc. ACM MMSys*, 123–128. doi:10.1145/1943552.1943569
- Milošević, M., Živić, N., Andjelković, I. (2017). Early Churn Prediction with Personalized Targeting in Mobile Social Games. *Expert Systems with Applications* 83, 326–332. doi:10.1016/j.eswa.2017.04.056
- Mustač, Bačić, Skorin-Kapov, Sužnjević (2022). Predicting Player Churn of a Free-to-Play Mobile Video Game Using Supervised Machine Learning. *Applied Sciences* 12(6), 2795. doi:10.3390/app12062795
- Niculescu-Mizil, A., Caruana, R. (2005). Predicting Good Probabilities with Supervised Learning. *Proc. ICML*, 625–632. doi:10.1145/1102351.1102430
- Saerens, M., Latinne, P., Decaestecker, C. (2002). Adjusting the Outputs of a Classifier to New a Priori Probabilities: A Simple Procedure. *Neural Computation* 14(1), 21–41. doi:10.1162/089976602753284446
- Saito, T., Rehmsmeier, M. (2015). The Precision-Recall Plot Is More Informative than the ROC Plot When Evaluating Binary Classifiers on Imbalanced Datasets. *PLOS ONE* 10(3), e0118432. doi:10.1371/journal.pone.0118432
- Siqueira, Rodrigues, Castanho, Jacobi (2017). A Data Analysis of Player in World of Warcraft Using Game Data Mining. *Proc. SBGames*, 445–451. doi:10.1109/SBGames.2017.00009
- Tarng, P.-Y., Chen, K.-T., Huang, P. (2008). An Analysis of WoW Players' Game Hours. *Proc. NetGames*, 47–52. doi:10.1145/1517494.1517504
- Tarng, P.-Y., Chen, K.-T., Huang, P. (2009). On Prophesying Online Gamer Departure. *Proc. NetGames*. doi:10.1109/NETGAMES.2009.5446225
