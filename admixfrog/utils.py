from collections import namedtuple, defaultdict
import numpy as np
import pandas as pd

Probs = namedtuple("Probs", ("O", "N", "P_cont", "alpha", "beta", "lib"))
Pars = namedtuple("Pars", ("alpha0", "trans_mat", "cont", "e0", "tau", "gamma_names"))
HAPX = (2699520, 155260560) #start, end of haploid region

class _IX:
    def __init__(self):
        pass

def data2probs(data, ref, state_ids, cont_id, state_priors=(.5, .5), cont_prior=(1,1)):
    alpha_ix = ["%s_alt" % s for s in state_ids]
    beta_ix = ["%s_ref" % s for s in state_ids]
    cont = "%s_alt" % cont_id, "%s_ref" % cont_id
    pa, pb = cont_prior

    print(alpha_ix, beta_ix)

    P = Probs(
        O = np.array(data.talt),
        N = np.array(data.tref + data.talt),
        P_cont = np.array( (data[cont[0]]+pa) / (data[cont[0]] + data[cont[1]]+ pa + pb)),
        alpha = np.array(ref[alpha_ix]) + state_priors[0],
        beta = np.array(ref[beta_ix]) + state_priors[1],
        lib = np.array(data.lib)
    )
    return P

def bins_from_bed(bed, data, bin_size, sex=None, pos_mode=False):
    """create a bunch of auxillary data frames for binning

    - bins: columns are chrom_id, chrom, bin_pos, bin_id, map
    - IX: container storing all indices, will need to be cleaned later on
    """
    IX = _IX()
    libs =np.unique(data.lib)
    if pos_mode:
        data.map = data.pos
        bed.map = bed.pos
    chroms = pd.unique(bed.chrom)
    snp = data[['chrom', 'pos', 'map']].drop_duplicates()
    n_snps = snp.shape[0]
    snp['snp_id'] = range(n_snps)
    snp['hap'] =  False

    if sex == 'm':
        snp.loc[ (data.chrom == 'X') & (HAPX[0] < data.pos) & (data.pos < HAPX[1]), 'hap'] = True


    IX.SNP2CHROMBIN = np.empty((n_snps,2), int)
    IX.SNP2BIN = np.empty((n_snps), int)
    IX.hapsnp = np.zeros(n_snps, bool)

    data = data.merge(snp)
    IX.OBS2SNP = np.array(data['snp_id'])

    bin_loc, data_loc = [], []
    bin0 = 0

    dtype_bin=  dtype=np.dtype([('chrom', 'U2'), ('map', float), ('pos', int), ('id',int),
                                ('chrom_id', int), ('hap', bool)])
    dtype_data=  dtype=np.dtype([('chrom', 'U2'), ('bin_id', int), ('snp_id',int),
                                 ('loc_id', int), ('chrom_id', int)])

    IX.bin_sizes = []

    for i, chrom in enumerate(chroms):
        map_ = bed.map[bed.chrom == chrom]
        pos = bed.pos[bed.chrom == chrom]
        map_data = data.map[data.chrom == chrom]

        chrom_start = float(np.floor(map_.head(1) / bin_size) * bin_size)
        chrom_end = float(np.ceil(map_.tail(1) / bin_size) * bin_size)

        bins = np.arange(chrom_start, chrom_end, bin_size)
        IX.bin_sizes.append( len(bins))
        bin_ids = range(bin0, bin0 + len(bins))
        _bin = np.empty_like(bins, dtype_bin)
        _bin['chrom'] = chrom
        _bin['pos'] = np.interp(bins, map_, pos)
        _bin['id'] = bin_ids
        _bin['map'] = bins
        _bin['chrom_id'] = i

        if chrom =='X' and sex == 'm':
            _bin['hap'] = (HAPX[0] < _bin['pos']) & (HAPX[1] > _bin['pos']) 
        else: 
            _bin['hap'] = False
        bin_loc.append(_bin)

        snp_ids = snp.snp_id[snp.chrom == chrom]
        dig_data = np.digitize(map_data, bins, right=False) - 1

        dig_snp = np.digitize(snp[snp.chrom==chrom].map, bins, right=False) -1
        IX.SNP2CHROMBIN[snp_ids, 0] = i
        IX.SNP2CHROMBIN[snp_ids, 1] = dig_snp
        IX.SNP2BIN[snp_ids] = dig_snp + bin0

        bin0 += len(bins)

    bins = np.hstack(bin_loc)


    IX.RG2OBS = dict((l, np.where(data.lib==l)[0]) for l in libs)
    IX.RG2SNP = dict((k, IX.OBS2SNP[v]) for k, v in IX.RG2OBS.items())
    IX.RG2BIN = dict((k, IX.SNP2BIN[v]) for k, v in IX.RG2SNP.items()) 
    IX.OBS2RG = np.array(data.lib)
    IX.OBS2BIN = IX.SNP2BIN[IX.OBS2SNP]
    IX.OBS2CHROMBIN = IX.SNP2CHROMBIN[IX.OBS2SNP]

    IX.HAPOBS = np.where(data.hap)[0]
    IX.HAPSNP = np.unique(IX.OBS2SNP[IX.HAPOBS])
    IX.DIPOBS = np.where(np.logical_not(data.hap))[0]
    IX.DIPSNP = np.unique(IX.OBS2SNP[IX.DIPOBS])
    IX.HAPBIN = bins['id'][bins['hap']]
    assert all(x in IX.HAPBIN for x in IX.SNP2BIN[IX.HAPSNP])
    assert all(x in IX.HAPBIN for x in IX.OBS2BIN[IX.HAPOBS])

    IX.n_chroms = len(chroms)
    IX.n_bins = len(bins)
    IX.n_snps = len(IX.SNP2BIN)
    IX.n_obs = len(IX.OBS2SNP)


    return bins, IX #, data_bin

def init_pars(state_ids, tau0=1., e0=1e-2, c0=1e-2):
    homo = [s for s in state_ids]
    het = []
    for i, s in enumerate(state_ids):
        for s2 in state_ids[i + 1 :]:
            het.append(s + s2)
    gamma_names = homo + het
    n_states = len(gamma_names)
    n_homo = len(state_ids)

    alpha0 = np.array([1 / n_states] * n_states)
    trans_mat = np.zeros((n_states, n_states)) + 2e-2
    np.fill_diagonal(trans_mat, 1 - (n_states - 1) * 2e-2)
    cont = defaultdict(lambda: c0)
    tau = [tau0] * n_homo
    return Pars(alpha0, trans_mat, cont, e0, tau, gamma_names)
