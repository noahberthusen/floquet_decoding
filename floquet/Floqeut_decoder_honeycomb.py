from numpy import *
import pylab
import os
import time
import re
from itertools import product as iterproduct
from random import random
from pymatching import Matching
from joblib import Parallel, delayed


# depolarization channel with total error probability p_err (p_err/3 for each Pauli error)
# step (0, 1, 2) is the last round of checks
def depolarize(p_err, step):
    err_path_step = num_edges * [0]
    err_path_step_p_one = num_edges * [0]
    syndroms = array([num_faces * [1] for _ in range(4)], dtype=uint8)
    errors = []

    for vert in range(num_sites):
        coin = random()
        if not coin < p_err:
            continue

        err_type = int(coin * 3 / p_err) # green, blue, red
        errors.append([vert, err_type])

        if err_type == step or (err_type + 1) % 3 == step:
            err_edge = err_edges[vert][step]
            err_path_step[err_edge] = 1 - err_path_step[err_edge]

            dual_edge = dual_edges[err_edge]
            syndroms[0][dual_edge[0]] *= -1
            syndroms[2][dual_edge[1]] *= -1
        if (err_type - 1) % 3 == step or (err_type + 1) % 3 == step:
            err_edge = err_edges[vert][(step + 1) % 3]
            err_path_step_p_one[err_edge] = 1 - err_path_step_p_one[err_edge]

            dual_edge = dual_edges[err_edge]
            syndroms[1][dual_edge[0]] *= -1
            syndroms[3][dual_edge[1]] *= -1

    return err_path_step, err_path_step_p_one, syndroms, errors

# double-depolarization channel on the qubit pairs that are about to be measured with total error prob p_err
# p_err/15 for each P1P2 that is errorenous
# step (0, 1, 2) is the last round of checks
def depolarize2(p_err, step):
    err_path_step = num_edges * [0]
    err_path_step_p_one = num_edges * [0]
    syndroms = array([num_faces * [1] for _ in range(4)], dtype=uint8)
    errors = []

    for i_e in [i for i in range(num_edges) if edge_colors[i] == (step+1) % 3]:
        coin = random()
        if not coin < p_err:
            continue

        err_type = int(coin * 15 / p_err) # XX, XY, XZ, XI, YX, YY, YZ, YI, ZX, ZY, ZZ, ZI, IX, IY, IZ
        errors.append([i_e, err_type])

        for vert, vert_err_type in zip(edges[i_e], [err_type // 4, err_type % 4]):
            if vert_err_type == 3:
                continue

            if vert_err_type == step or (vert_err_type + 1) % 3 == step:
                err_edge = err_edges[vert][step]
                err_path_step[err_edge] = 1 - err_path_step[err_edge]

                dual_edge = dual_edges[err_edge]
                syndroms[0][dual_edge[0]] *= -1
                syndroms[2][dual_edge[1]] *= -1
            if (vert_err_type - 1) % 3 == step or (vert_err_type + 1) % 3 == step:
                err_edge = err_edges[vert][(step + 1) % 3]
                err_path_step_p_one[err_edge] = 1 - err_path_step_p_one[err_edge]

                dual_edge = dual_edges[err_edge]
                syndroms[1][dual_edge[0]] *= -1
                syndroms[3][dual_edge[1]] *= -1

    return err_path_step, err_path_step_p_one, syndroms, errors

# measurement error channel with probability p_err of reporting the wrong value after measrement
# step (0, 1, 2) is the last round of checks
def measurement_error(p_err, step):
    err_path_step = num_edges * [0]
    err_path_step_p_one = num_edges * [0]
    syndroms = array([num_faces * [1] for _ in range(5)], dtype=uint8)
    errors = []

    for i_e in [i for i in range(num_edges) if edge_colors[i] == (step+1) % 3]:
        if not random() < p_err:
            continue

        errors.append(i_e)

        err_path_step[i_e] = 1 - err_path_step[i_e]
        err_path_step_p_one[i_e] = 1 - err_path_step_p_one[i_e]

        dual_edge = dual_edges[i_e]
        syndroms[0][dual_edge[1]] *= -1
        syndroms[3][dual_edge[1]] *= -1
        syndroms[1][dual_edge[0]] *= -1
        syndroms[4][dual_edge[0]] *= -1

    return err_path_step, err_path_step_p_one, syndroms, errors

# EM3 channel from 'A fault-tolerant honeycomb memory'
# step (0, 1, 2) is the last round of checks
def em3_channel(p_err, step):
    err_path_step = num_edges * [0]
    err_path_step_p_one = num_edges * [0]
    syndroms = array([num_faces * [1] for _ in range(5)], dtype=uint8)
    dep_errors = []
    meas_errors = []

    for i_e in [i for i in range(num_edges) if edge_colors[i] == (step+1) % 3]:
        coin = random()
        if not coin < p_err:
            continue

        # 2-depolarization error
        err_type = int(coin * 15 / p_err) # XX, XY, XZ, XI, YX, YY, YZ, YI, ZX, ZY, ZZ, ZI, IX, IY, IZ
        dep_errors.append([i_e, err_type])

        for vert, vert_err_type in zip(edges[i_e], [err_type // 4, err_type % 4]):
            if vert_err_type == 3:
                continue

            if vert_err_type == (step+1)%3 or (vert_err_type + 1) % 3 == (step+1)%3:
                err_edge = err_edges[vert][(step+1)%3]
                err_path_step_p_one[err_edge] = 1 - err_path_step_p_one[err_edge]

                dual_edge = dual_edges[err_edge]
                syndroms[1][dual_edge[0]] *= -1
                syndroms[3][dual_edge[1]] *= -1
            if (vert_err_type - 1) % 3 == (step+1)%3 or (vert_err_type + 1) % 3 == (step+1)%3:
                err_edge = err_edges[vert][((step+1)%3 + 1) % 3]
                err_path_step[err_edge] = 1 - err_path_step[err_edge]

                dual_edge = dual_edges[err_edge]
                syndroms[2][dual_edge[0]] *= -1
                syndroms[4][dual_edge[1]] *= -1

        # measurement error
        if not random() < 0.5:
            continue

        meas_errors.append(i_e)

        err_path_step[i_e] = 1 - err_path_step[i_e]
        err_path_step_p_one[i_e] = 1 - err_path_step_p_one[i_e]

        dual_edge = dual_edges[i_e]
        syndroms[0][dual_edge[1]] *= -1
        syndroms[3][dual_edge[1]] *= -1
        syndroms[1][dual_edge[0]] *= -1
        syndroms[4][dual_edge[0]] *= -1

    return err_path_step, err_path_step_p_one, syndroms, dep_errors, meas_errors

def save_st_lattice():
    txt_file = open(folder_name + f"/spacetime_edges.txt", 'w')
    txt_file.write('\n'.join([' '.join([f"{edge[0][0]}", f"{edge[0][1]}", f"{edge[1][0]}", f"{edge[1][1]}"]) for edge in spacetime_lattice_edges]))
    txt_file.close()

def calc_recovery(p_depol, p_depol2 = 0, p_meas = 0, p_em3 = 0, meas_heuristic = False):
    time_0 = time.time()

    matching = Matching(HH)
    num_shots = 100
    shots_res = []
    p_rec = 0.5
    std_rec = 1

    while (std_rec+1e-9) / (1-p_rec+1e-9) / log(10) > 0.05 and len(shots_res) < 10000:
        for shot in range(num_shots):
            shots_res.append(1)

            # Applying errors and extracting syndroms
            err_path_odd = num_edges * [0]
            err_path_even = num_edges * [0]
            syndroms = array([num_faces * [1] for _ in range(num_steps)], dtype=uint8)
            for step in range(num_steps - num_final_steps):
                # depolarization errors
                if p_depol > 0:
                    err_path_step, err_path_step_p_one, cur_syndroms, _ = depolarize(p_depol, (step-1) % 3)

                    if step % 2 == 0:
                        err_path_even = [(err_path_even[i_e] + err_path_step[i_e]) % 2 for i_e in range(num_edges)]
                        err_path_odd = [(err_path_odd[i_e] + err_path_step_p_one[i_e]) % 2 for i_e in range(num_edges)]
                    else:
                        err_path_even = [(err_path_even[i_e] + err_path_step_p_one[i_e]) % 2 for i_e in range(num_edges)]
                        err_path_odd = [(err_path_odd[i_e] + err_path_step[i_e]) % 2 for i_e in range(num_edges)]

                    syndroms[step:step+4, :] *= cur_syndroms

                # double-depolarization errors
                if p_depol2 > 0:
                    err_path_step, err_path_step_p_one, cur_syndroms, _ = depolarize2(p_depol2, (step-1) % 3)

                    if step % 2 == 0:
                        err_path_even = [(err_path_even[i_e] + err_path_step[i_e]) % 2 for i_e in range(num_edges)]
                        err_path_odd = [(err_path_odd[i_e] + err_path_step_p_one[i_e]) % 2 for i_e in range(num_edges)]
                    else:
                        err_path_even = [(err_path_even[i_e] + err_path_step_p_one[i_e]) % 2 for i_e in range(num_edges)]
                        err_path_odd = [(err_path_odd[i_e] + err_path_step[i_e]) % 2 for i_e in range(num_edges)]

                    syndroms[step:step+4, :] *= cur_syndroms

                # measurement errors
                if p_meas > 0:
                    err_path_step, err_path_step_p_one, cur_syndroms, _ = measurement_error(p_meas, (step-1) % 3)

                    if step % 2 == 0:
                        err_path_even = [(err_path_even[i_e] + err_path_step[i_e]) % 2 for i_e in range(num_edges)]
                        err_path_odd = [(err_path_odd[i_e] + err_path_step_p_one[i_e]) % 2 for i_e in range(num_edges)]
                    else:
                        err_path_even = [(err_path_even[i_e] + err_path_step_p_one[i_e]) % 2 for i_e in range(num_edges)]
                        err_path_odd = [(err_path_odd[i_e] + err_path_step[i_e]) % 2 for i_e in range(num_edges)]

                    syndroms[step:step+5, :] *= cur_syndroms

                # EM3 channel from 'A fault-tolerant honeycomb memory'
                if p_em3 > 0:
                    err_path_step, err_path_step_p_one, cur_syndroms, _, _ = em3_channel(p_em3, (step-1) % 3)

                    if step % 2 == 0:
                        err_path_even = [(err_path_even[i_e] + err_path_step[i_e]) % 2 for i_e in range(num_edges)]
                        err_path_odd = [(err_path_odd[i_e] + err_path_step_p_one[i_e]) % 2 for i_e in range(num_edges)]
                    else:
                        err_path_even = [(err_path_even[i_e] + err_path_step_p_one[i_e]) % 2 for i_e in range(num_edges)]
                        err_path_odd = [(err_path_odd[i_e] + err_path_step[i_e]) % 2 for i_e in range(num_edges)]

                    syndroms[step:step+5, :] *= cur_syndroms

            # Correcting the errors only based on syndroms
            correction_path_odd = zeros(num_edges, dtype=uint8)
            correction_path_even = zeros(num_edges, dtype=uint8)

            correction = matching.decode([0 if synd == 1 else 1 for synd in concatenate(syndroms)])
            for st_edge in range(num_st_edges):
                if correction[st_edge] == 1:
                    if spacetime_lattice_edges[st_edge][1][0] % 2 == 0:
                        correction_path_even[ies_st_lattice[st_edge]] = 1 - correction_path_even[ies_st_lattice[st_edge]]
                    else:
                        correction_path_odd[ies_st_lattice[st_edge]] = 1 - correction_path_odd[ies_st_lattice[st_edge]]

            # Checking for logical errors
            total_err_even = (err_path_even + correction_path_even) % 2
            total_err_odd = (err_path_odd + correction_path_odd) % 2
            for loop in non_triv_loops:
                if sum(loop * total_err_even) % 2 == 1 or sum(loop * total_err_odd) % 2 == 1:
                    shots_res[-1] = 0
                    break

        p_rec = average(shots_res)
        std_rec = std(shots_res) / sqrt(len(shots_res) - 1)

        num_shots *= 2

    return p_rec, std_rec, len(shots_res), int((time.time() - time_0)*100)/100



num_sites = 24
folder_name = f"6_3_lattices/C{num_sites}.1"


print(f"{folder_name} lattice selected")

# Geometrical parameters
pp = 6
qq = 3

num_edges = num_sites * qq // 2
num_faces = num_sites * qq // pp
gg = 1


# Reading lattice data
edges = []
edge_colors = []  # 0 for green (XX), 1 for blue (YY), 2 for red (ZZ)
err_edges = [3 * [-1] for _ in range(num_sites)] # correcoponding edge for each error type on a vertex
for i_c in range(3):
    color = {0: 'green', 1: 'blue', 2: 'red'}[i_c]
    txt_file = open(folder_name + f"/" + color + f"_adj_mat.txt", 'r')
    for line in txt_file:
        edge = [int(i) for i in re.split(' ', line.strip()) if i != '']
        edges.append(edge)
        edge_colors.append(i_c)
        err_edges[edge[0]][i_c] = len(edges)-1
        err_edges[edge[1]][i_c] = len(edges)-1

non_triv_loops = [num_edges * [0] for _ in range(2*gg)]  # in terms of edge incidents
txt_file = open(folder_name + f"/nontriv_loops.txt", 'r')
for i_l, line in enumerate(txt_file):
    loop_verts = [int(i) for i in re.split(' ', line.strip()) if i != '']
    for i_vert in range(len(loop_verts)):
        edge_i = [loop_verts[i_vert], loop_verts[i_vert + 1 - len(loop_verts)]]
        non_triv_loops[i_l][edges.index(list(sort(edge_i)))] = 1

faces = []
face_colors = []
txt_file = open(folder_name + f"/plaquettes.txt", 'r')
for line in txt_file:
    face = [int(i) for i in re.split(' ', line.strip()) if i != '']
    faces.append(face)
    face_colors.append(3 - edge_colors[edges.index(list(sort(face[:2])))] - edge_colors[edges.index(list(sort(face[1:3])))])

# Generating dual lattice edges
dual_edges = []
for edge in edges:
    dual_edge = [i_f for i_f, face in enumerate(faces) if (edge[0] in face) and ((face[(face.index(edge[0])+1) % pp] == edge[1]) or (face[(face.index(edge[0])-1) % pp] == edge[1]))]
    if (face_colors[dual_edge[1]] - face_colors[dual_edge[0]]) % 3 != 2:
        dual_edge = list(flip(dual_edge))
    dual_edges.append(dual_edge)

# Generating the edges of space-time lattice in [[plaquette1, plaquette2], [time1, time2]] format
num_steps = 8 # each Floquet period is 3 steps
num_final_steps = 5 # at least 3 for depolarization and at least 4 for measurement error
spacetime_lattice_edges = []
ies_st_lattice = []
for i_e, dual_edge in enumerate(dual_edges):
    synd_round = (edge_colors[i_e] + 1) % 3
    for period in range(num_steps // 3):
        spacetime_lattice_edges.append([dual_edge, [3*period+synd_round, 3*period+synd_round+2]])
        ies_st_lattice.append(i_e)
num_st_edges = len(spacetime_lattice_edges)


# H matrix for PyMatching
HH = zeros((num_steps * num_faces, num_st_edges), dtype=uint8)
for i_e, st_edge in enumerate(spacetime_lattice_edges):
    HH[st_edge[0][0] + num_faces * st_edge[1][0]][i_e] = 1
    HH[st_edge[0][1] + num_faces * st_edge[1][1]][i_e] = 1
matching = Matching(HH)



p_errs = 10 ** linspace(-4.1, -2.1, 3)
p_recs = []
std_recs = []
num_shotss = []


# for p_err in p_errs:
#     print(calc_recovery(p_depol=0, p_meas=0, p_em3=p_err))
rec_res = Parallel(n_jobs=3)(delayed(calc_recovery)(p_depol=0, p_meas=0, p_em3=p_err) for p_err in p_errs)

for i_p, p_err in enumerate(p_errs):
    p_rec = rec_res[i_p][0]
    std_rec = rec_res[i_p][1]
    num_shots = rec_res[i_p][2]

    print(f"p_err = {round(100000*p_err)/100000}: p_rec = {round(100000*p_rec)/100000} +- {round(100000*std_rec)/100000} ({num_shots} shots) ({rec_res[i_p][3]} s)")
    p_recs.append(p_rec)
    std_recs.append(std_rec)
    num_shotss.append(num_shots)