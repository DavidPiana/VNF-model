# =====================================================================
# MODELLO SUPERATO: Ottimizzazione del parametro "Big-M" in base alla specifica VNF.
#  Model Formulation 3
#  VNF placement + Service Function Chain routing
#  Objective: minimize the maximum end-to-end latency (Lmax)
#
#  Notation mapping LaTeX -> AMPL (only where names had to change):
#    tau (virtual sink node)        -> TAUNODE   (symbolic parameter)
#    tau_ij (transport delay)       -> delay{A}
#    u (arc capacity)                -> capArc    (renamed: "u" is used as a
#                                                    dummy index in (9)-(10))
#    d^k (bandwidth demand)          -> dem{D}
#    f(s) (chain function)           -> chain{1..n}
# =====================================================================

# ----------------------------- SETS ---------------------------------
set N;                        # physical nodes
set A within {N,N};           # physical arcs (directed)
set D;                        # demands
set F;                        # VNF (service) types

param n integer > 0;          # number of services in the chain (same for all demands)

param TAUNODE symbolic;       # label used for the virtual sink node tau
check: TAUNODE not in N;

set NPLUS := N union {TAUNODE};                       # N+ = N u {tau}
set APLUS := A union (setof {i in N} (i, TAUNODE));   # A+ = A u {(i,tau): i in N}

# --------------------------- PARAMETERS ------------------------------
param capArc >= 0;              # capacity u of each physical arc (not used by any constraint below)
param q{F} >= 0;                 # capacity q_f of VNF type f
param dem{D} >= 0;                # bandwidth demand d^k of demand k (not used by any constraint below)

# Parametri training time F2 (federated learning)
param c_batch;
param c_inv_matr {1..3};
param q_batch;
param q_inv_matr {1..3};
param lv {N} default 1;
param T_target >= 0;
param DS_max >= 0;

param o{D} symbolic;              # origin node o^k of demand k
check {k in D}: o[k] in N;

set O := setof {k in D} o[k];     # O = { o^k : k in D }

param chain{1..n} symbolic;       # chain function f(s): position s -> VNF type
check {s in 1..n}: chain[s] in F;

param alpha{i in N, f in F} default 0;   # alpha_{i,f}
check {i in N, f in F}: alpha[i,f] = 0 or alpha[i,f] = 1;
check {i in O, f in F}: alpha[i,f] = 0;   # alpha_{i,f}=1 requires i not in O

param delay{A} >= 0;               # transport delay tau_ij on physical arc (i,j)
param sigma{F} >= 0;                # fixed setup time of VNF type f
param gamma{F} >= 0;                # variable processing time per demand for VNF type f

# big-M per funzione: limita T[i,f] al massimo valore possibile per ogni f
# F1/F3: sigma + gamma*|D|;  F2: T_target;  F4: 0
param Mf_base {f in F} := sigma[f] + gamma[f] * card(D);
param Mf_F2 := max {lv_idx in 1..3}
    ((q_batch + q_inv_matr[lv_idx]) + (c_batch + c_inv_matr[lv_idx]) * card(D));
param Mf {f in F} := if f = 'F2' then
    (if Mf_F2 < T_target then Mf_F2 else T_target)
  else Mf_base[f];

# --------------------------- VARIABLES --------------------------------
var y{N,F} binary;                  # y_{i,f}
var z{D,N,F} binary;                # z_{i,f}^k
var x{D, APLUS, 1..n+1} binary;     # x_{ij}^{ks}
var w{N, APLUS, 1..n} binary;       # w_{uv}^{i,s+1}  (index s = 1..n stands for s+1 = 2..n+1)
var T{N,F} >= 0;                    # T_{i,f}
var Theta{D,N,F} >= 0;              # Theta_{i,f}^k
var L{D} >= 0;                      # L^k
var Lmax >= 0;                      # L_max

# --------------------------- OBJECTIVE ---------------------------------
minimize Obj_MaxLatency: Lmax;

# --------------------------- CONSTRAINTS --------------------------------

# (1) VNF assignment: each demand uses exactly one instance of each VNF type
subject to Assign1 {k in D, f in F}:
    sum {i in N} z[k,i,f] = 1;

# (2a) usage requires installation
subject to Assign2a {k in D, i in N, f in F: alpha[i,f] = 1}:
    z[k,i,f] <= y[i,f];

# (2b) usage forbidden where alpha = 0
subject to Assign2b {k in D, i in N, f in F: alpha[i,f] = 0}:
    z[k,i,f] = 0;

# (2c) installation forbidden where alpha = 0
subject to Assign2c {i in N, f in F: alpha[i,f] = 0}:
    y[i,f] = 0;

# (3) VNF instance capacity
subject to CapVNF {i in N, f in F: alpha[i,f] = 1}:
    sum {k in D} z[k,i,f] <= q[f];

# (4) intermediate flow balance (s = 2..n)
subject to FlowInter {k in D, i in N, s in 2..n}:
      sum {j in NPLUS: (i,j) in APLUS} x[k,i,j,s]
    - sum {j in N: (j,i) in A} x[k,j,i,s]
    = z[k,i,chain[s-1]] - z[k,i,chain[s]];

# (5) first-subpath flow balance (s = 1)
subject to FlowFirst {k in D, i in N}:
      sum {j in N: (i,j) in A} x[k,i,j,1]
    - sum {j in N: (j,i) in A} x[k,j,i,1]
    = (if i = o[k] then 1 else 0) - z[k,i,chain[1]];

# (6) last-subpath flow balance (s = n+1)
subject to FlowLast {k in D, i in N}:
      sum {j in NPLUS: (i,j) in APLUS} x[k,i,j,n+1]
    - sum {j in N: (j,i) in A} x[k,j,i,n+1]
    = z[k,i,chain[n]];

# (7) in-degree <= 1 (simple path, no cycles/splitting)
subject to InDegree {k in D, i in N}:
    sum {s in 1..n+1} sum {j in N: (j,i) in A} x[k,j,i,s] <= 1;

# (8) out-degree <= 1
subject to OutDegree {k in D, i in N}:
    sum {s in 1..n+1} sum {j in NPLUS: (i,j) in APLUS} x[k,i,j,s] <= 1;

# (9) path-unification (coupling)
subject to Coupling {k in D, i in N, (u,v) in APLUS, s in 1..n}:
    x[k,u,v,s+1] <= w[i,u,v,s] + (1 - z[k,i,chain[s]]);

# (10) no bifurcation of aggregated paths
subject to NoBifurcation {u in N, i in N, s in 1..n}:
    sum {v in NPLUS: (u,v) in APLUS} w[i,u,v,s] <= 1;

# (11a) processing time per F2 (federated learning)
subject to ProcTimeF2 {i in N: alpha[i,'F2'] = 1}:
    T[i,'F2'] = (c_batch + c_inv_matr[lv[i]]) * sum {k in D} z[k,i,'F2']
              + (q_batch + q_inv_matr[lv[i]]) * y[i,'F2'];

# (11b) processing time for other functions
subject to ProcTimeOther {i in N, f in F: f != 'F2' and alpha[i,f] = 1}:
    T[i,f] = sigma[f]*y[i,f] + gamma[f]*sum {k in D} z[k,i,f];

# (12)-(13) linearisation of Theta_{i,f}^k
subject to Theta1 {k in D, i in N, f in F: alpha[i,f] = 1}:
    Theta[k,i,f] <= Mf[f] * z[k,i,f];

subject to Theta2 {k in D, i in N, f in F: alpha[i,f] = 1}:
    Theta[k,i,f] >= T[i,f] - Mf[f]*(1 - z[k,i,f]);

# (14) end-to-end latency
subject to Latency {k in D}:
    L[k] = sum {s in 1..n+1} sum {(i,j) in A} delay[i,j]*x[k,i,j,s]
         + sum {i in N, f in F: alpha[i,f] = 1} Theta[k,i,f];

# (15) maximum latency
subject to MaxLatencyLink {k in D}:
    Lmax >= L[k];

# (16) capacity of F2 (DS_max)
subject to CapF2 {i in N: alpha[i,'F2'] = 1}:
    sum {k in D} z[k,i,'F2'] <= DS_max;

# (17) federated learning training time convergence target
subject to TrainingTarget {i in N: alpha[i,'F2'] = 1}:
    T[i,'F2'] <= T_target;

# (18) massimo 3 nodi AIF per F4
subject to MaxNodesF4:
    sum {i in N: alpha[i,'F4'] = 1} y[i,'F4'] <= 3;

# Housekeeping: pin unused T / Theta to zero where alpha = 0
subject to TZero {i in N, f in F: alpha[i,f] = 0}:
    T[i,f] = 0;

subject to ThetaZero {k in D, i in N, f in F: alpha[i,f] = 0}:
    Theta[k,i,f] = 0;
