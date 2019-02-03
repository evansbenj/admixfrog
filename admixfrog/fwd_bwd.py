from numba import njit
import numpy as np

@njit
def calc_ll(alpha0, trans_mat, emissions):
    """likelihood using forward algorithm"""
    _, n = fwd_algorithm(alpha0, emissions, trans_mat=trans_mat)
    return np.sum([np.sum(np.log(n_)) for n_ in n])
@njit
def fwd_step(alpha_prev, E, trans_mat):
    alpha_new = (alpha_prev @ trans_mat) * E
    n = np.sum(alpha_new)
    return alpha_new / n, n


@njit
def fwd_algorithm_single_obs(alpha0, emission, trans_mat):
    """
    calculate P(X_t | o_[1..t], a0)
    =P(X_t , o_[1..t], a0 | o_[1..t])
    """
    n_steps, n_states = emission.shape
    alpha = np.empty((n_steps + 1, n_states))
    n = np.empty((n_steps + 1))
    alpha[0] = alpha0
    n[0] = np.sum(alpha0)
    for i in range(n_steps):
        alpha[i + 1], n[i + 1] = fwd_step(alpha[i], emission[i], trans_mat)
    return alpha, n
# @jit(nopython=True)
def fwd_algorithm(alpha0, emissions, trans_mat):
    """
    calculate P(X_t | o_[1..t], a0)
    =P(X_t , o_[1..t], a0 | o_[1..t])
    """
    # alpha, n = [], []
    n_seqs = len(emissions)
    alpha = [np.empty((2, 2)) for _ in range(n_seqs)]
    n = [np.empty((2)) for _ in range(n_seqs)]
    for i in range(n_seqs):
        alpha[i], n[i] = fwd_algorithm_single_obs(alpha0, emissions[i], trans_mat)
    return alpha, n


@njit
def bwd_step(beta_next, E, trans_mat, n):
    beta = (trans_mat * E) @ beta_next
    return beta / n


@njit
def bwd_algorithm_single_obs(emission, trans_mat, n):
    """
    calculate P(o[t+1..n] | X) / P(o[t+1..n])
    """

    n_steps, n_states = emission.shape

    beta = np.empty((n_steps + 1, n_states))
    beta[n_steps] = 1

    # for i, e in zip(range(n_steps-1, -1, -1), reversed(em)):
    for i in range(n_steps - 1, -1, -1):
        beta[i] = bwd_step(beta[i + 1], emission[i], trans_mat, n[i + 1])
    return beta

# @jit(nopython=True)
def bwd_algorithm(emissions, trans_mat, n):
    """
    calculate P(o[t+1..n] | X) / P(o[t+1..n])

    emissions : list[np.array] 
        list of emission probabilities, one per observed sequence (i.e. chromosome)
    n : list[np.array]
        list of normalization constants
    trans_mat : np.array<n_states x n_states>
        transition matrix
    """

    n_seqs = len(emissions)
    beta = [np.empty((2, 2)) for _ in range(n_seqs)]
    for i in range(n_seqs):
        n_i, em = n[i], emissions[i]
        n_steps, n_states = em.shape
        beta_i = bwd_algorithm_single_obs(em, trans_mat, n_i)
        beta[i] = beta_i
    return beta
# @jit(nopython=True)
def fwd_bwd_algorithm(alpha0, emissions, trans_mat):
    alpha, n = fwd_algorithm(alpha0=alpha0, emissions=emissions, trans_mat=trans_mat)
    beta = bwd_algorithm(emissions=emissions, n=n, trans_mat=trans_mat)
    gamma = [a * b for (a, b) in zip(alpha, beta)]
    # for g in gamma:
    #    assert np.allclose(np.sum(g, 1), 1)
    return alpha, beta, gamma, n

def viterbi(alpha0, trans_mat, emissions):
    return [viterbi_single_obs(alpha0, trans_mat, e) for e in emissions]


def viterbi_single_obs(alpha0, trans_mat, emissions):
    n_steps, n_states = emissions.shape

    ll = np.ones_like(emissions)
    backtrack = np.zeros_like(emissions, int)

    log_e = np.log(emissions)
    log_t = np.log(trans_mat)

    for i in range(n_steps):
        if i == 0:
            aux_mat = np.log(alpha0) + log_t + log_e[0]
        else:
            aux_mat = ll[i - 1] + log_t + log_e[i]
        ll[i] = np.max(aux_mat, 1)
        backtrack[i] = np.argmax(aux_mat, 1)

    path = np.empty(n_steps)
    cursor = np.argmax(ll[-1])
    for i in range(n_steps - 1, -1, -1):
        cursor = backtrack[i, cursor]
        path[i] = cursor

    return path