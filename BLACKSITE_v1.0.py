#!/usr/bin/env python3

"""
BLACKSITE v1.0
Persistent spectral tracking and signal analysis workstation
"""

import sys
import os
if getattr(sys, "frozen", False):
    mpl_config_dir = os.path.join(os.path.expanduser("~"), ".blacksite", "matplotlib")
    os.makedirs(mpl_config_dir, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = mpl_config_dir
import wave
import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
import csv
from bisect import bisect_left, bisect_right
import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.qt_compat import QtWidgets
from matplotlib.widgets import Button, RangeSlider
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import copy
from matplotlib.patches import Rectangle
import time as tm
from matplotlib.ticker import FuncFormatter
from matplotlib.backends.qt_compat import QtWidgets
plt.rcParams['font.family'] = 'monospace'

def system_input(file_path):
    time = []
    time_matches = []
    time_unit = None
    seconds = ['s', 'sec', 'secs', 'second', 'seconds']
    milliseconds = ['ms', 'millisecond', 'milliseconds']
    microseconds = ['us', 'µs', 'microsecond', 'microseconds']
    nanoseconds = ['ns', 'nanosecond', 'nanoseconds']
    signal_matches = []
    signal = []
    name_mapping = {}
    accepted_time = ['time', 'timestamp', 'timestamps', 't', 'sec', 'secs', 'second', 'seconds', 'time_s', 'time_sec', 'time_secs', 'time_second', 'time_seconds', 'elapsed_time', 'elapsed', 'elapsed_s', 'elapsed_sec', 'sample_time', 'sample_timestamp', 'relative_time', 'relative_time_s']
    accepted_signal = ['signal', 'amplitude', 'value', 'sample', 'measurement', 'reading', 'signal_value', 'signal_amplitude', 'amplitude_value', 'sample_value', 'measured_value', 'measurement_value', 'sensor_value', 'sensor_reading', 'channel', 'channel_1', 'ch1', 'input', 'input_signal']
    try:
        with open(file_path, encoding='utf-8-sig', newline='') as csv_raw:            
            try:
                sniffer = csv.Sniffer()
                sample = csv_raw.read(2048)
                dialect = sniffer.sniff(sample, ',;\t')
                csv_raw.seek(0)
            except csv.Error:
                return
            dict_csv = csv.DictReader(csv_raw, dialect = dialect)
            if dict_csv.fieldnames is None:
                return
            for names in dict_csv.fieldnames:
                clean = names.strip()
                clean = clean.lower()
                base = clean
                unit = None
                if '(' in clean and ')' in clean:
                    start = clean.find('(')
                    end = clean.find(')')
                    base = clean[0:start]
                    base = base.strip()
                    unit = clean[start + 1:end]
                    unit = unit.strip()
                elif '[' in clean and ']' in clean:
                    start = clean.find('[')
                    end = clean.find(']')
                    base = clean[0:start]
                    base = base.strip()
                    unit = clean[start + 1:end]
                    unit = unit.strip()
                base = base.replace(' ', '_')
                if base in accepted_time:
                    time_matches.append(base)
                    chosen_time = base
                    time_unit = unit
                    if time_unit is not None and time_unit not in seconds and time_unit not in milliseconds and time_unit not in microseconds and time_unit not in nanoseconds:
                        return
                    elif time_unit is None:
                        time_unit = 's'
                if base in accepted_signal:
                    signal_matches.append(base)
                    chosen_signal = base
                name_mapping[base] = names
            if len(time_matches) != 1 or len(signal_matches) != 1:
                return
            for j in dict_csv:
                str_time = j[name_mapping[chosen_time]]
                str_signal = j[name_mapping[chosen_signal]]
                try:
                    flt_time = float(str_time)
                    flt_signal = float(str_signal)
                    if time_unit in milliseconds:
                        flt_time = flt_time / 1000
                    elif time_unit in microseconds:
                        flt_time = flt_time * 1e-6
                    elif time_unit in nanoseconds:
                        flt_time = flt_time * 1e-9
                    time.append(flt_time)
                    signal.append(flt_signal)
                except (ValueError, TypeError):
                    return
        time = np.array(time)
        signal = np.array(signal)
        if len(time) < 2 or len(signal) < 2:
            return
        if len(time) != len(signal):
            return
        if np.all(np.isfinite(time)) == False:
            return
        if np.all(np.isfinite(signal)) == False:
            return
        difference = np.diff(time)
        if np.any(difference <= 0):
            return
        med_diff = np.median(difference)
        sample_min = int(round(1 / med_diff))
        if len(signal) < sample_min:
            return
        upper = med_diff * 1.01
        lower = med_diff * 0.99
        if np.any((difference > upper) | (difference < lower)):
            return
        return signal, time
    except (FileNotFoundError, PermissionError, IsADirectoryError):
        return

def wav_input(file_path):
    try:
        with wave.open(file_path, 'rb') as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()
            compression = wav_file.getcomptype()
            if compression != 'NONE':
                return
            raw = wav_file.readframes(frame_count)
        if sample_width == 1:
            signal = np.frombuffer(raw, dtype=np.uint8).astype(float)
            signal = (signal - 128) / 128
        elif sample_width == 2:
            signal = np.frombuffer(raw, dtype='<i2').astype(float)
            signal = signal / 32768
        elif sample_width == 3:
            # NumPy has no native int24 dtype, so I have to reconstruct each little endian
            # 24-bit PCM sample from three bytes inside an int32 container
            signal = np.frombuffer(raw, dtype=np.uint8)
            signal = signal.reshape(-1, 3)
            signal = signal.astype(np.int32)
            signal = signal[:, 0] | (signal[:, 1] << 8) | (signal[:, 2] << 16)
            # Convert reconstructed 24-bit values into signed samples
            negative = signal >= 8388608
            signal[negative] = signal[negative] - 16777216
            # Normalize signed 24-bit PCM to be approximately in between -1 and 1.
            signal = signal.astype(float)
            signal = signal/8388608
        elif sample_width == 4:
            signal = np.frombuffer(raw, dtype='<i4').astype(float)
            signal = signal / 2147483648
        else:
            return
        if channels > 1:
            signal = signal.reshape(-1, channels)
            signal = np.mean(signal, axis=1)
        if len(signal) < sample_rate:
            return
        if np.all(np.isfinite(signal)) == False:
            return
        time = np.arange(len(signal)) / sample_rate
        return signal, time
    except (wave.Error, FileNotFoundError, PermissionError, IsADirectoryError):
        return    

def window_extract(signal, time, start_sample, window_size, step):
    windows = []
    short_mid_time = []
    short_window_index = []
    for i in range(1+(len(signal)-window_size)//step):
        start=i*step
        end=start+window_size
        window=signal[start:end]
        windows.append(window)
        center=start+window_size//2
        time_center=time[center]
        short_mid_time.append(time_center)
        global_window_index = (start_sample + start)//step
        short_window_index.append(global_window_index)
    return windows, short_mid_time, short_window_index

def window_fft(windows, short_mid_time, time):
    short_magnitude=[]
    for i in range(len(windows)):
        window=windows[i]
        hann=np.hanning(len(window))
        window_hann=window*hann
        fft_result=np.fft.fft(window_hann)
        fft_magnitude=np.abs(fft_result)*(2/(np.sum(hann)))
        short_frequency=np.fft.fftfreq(len(window_hann), d=time[1]-time[0])
        positive=short_frequency>=0
        fft_magnitude=fft_magnitude[positive]
        short_frequency=short_frequency[positive]
        short_magnitude.append(fft_magnitude)
    return short_magnitude, short_frequency, short_mid_time

def window_fft_high(signal, time, start_sample, window_size, step):
    long_windows, long_mid_time, _ = window_extract(signal, time, start_sample, window_size, step)
    long_magnitude, long_frequency, long_mid_time = window_fft(long_windows, long_mid_time, time)
    return long_magnitude, long_frequency, long_mid_time

def auto_threshold(short_magnitude):
    noise_floor=np.median(short_magnitude)
    threshold=noise_floor+np.std(short_magnitude)*3
    return threshold

def window_peak(magnitude, frequency):
    threshold = auto_threshold(magnitude)
    short_magnitude=[]
    short_frequency=[]
    for i in range(1, len(magnitude)-1):
        n=magnitude[i]
        if n>threshold and n>magnitude[i-1] and n>magnitude[i+1]:
            short_magnitude.append(n)
            short_frequency.append(frequency[i])
    short_magnitude=np.array(short_magnitude)
    short_frequency=np.array(short_frequency)
    order=np.argsort(short_magnitude)
    short_magnitude=short_magnitude[order][::-1]
    short_frequency=short_frequency[order][::-1]
    return short_magnitude, short_frequency

def peak_detection(short_magnitude, short_frequency, short_mid_time):
    peak_magnitudes=[]
    peak_frequency=[]
    for mag in short_magnitude:
        peak_mag, peak_freq = window_peak(mag, short_frequency)
        peak_magnitudes.append(peak_mag)
        peak_frequency.append(peak_freq)
    return peak_magnitudes, peak_frequency, short_mid_time

def frequency_refining(peak_frequency, short_frequency, short_mid_time, magnitude_res, frequency_res, mid_time_res):
    bins = short_frequency[1] - short_frequency[0]
    refined_results = []
    for f in range(len(peak_frequency)):
        freq_ref = []
        rough_list = []
        window_freq = peak_frequency[f]
        if len(window_freq) > 0:
            for k in range(len(window_freq)):
                rough_list.append(window_freq[k])            
            time = short_mid_time[f]
            time_diff = np.abs(time - mid_time_res)
            window_index = np.argmin(time_diff)
            list_mags = magnitude_res[window_index]
            long_time = mid_time_res[window_index]
            threshold = auto_threshold(list_mags)
            mags_index = []
            for i in range(1, len(list_mags) - 1):
                n = list_mags[i]
                if n > threshold and n > list_mags[i - 1] and n > list_mags[i + 1]:
                    mags_index.append(i)
            for z in range(len(mags_index)):
                freq_ref.append(frequency_res[mags_index][z])
            rough_peak_refined = []
            for _ in range(len(rough_list)):
                rough_peak_refined.append([])
            for t in range(len(freq_ref)):
                rough_peak_index = np.argmin(np.abs(freq_ref[t] - rough_list))
                nearest_peak = rough_list[rough_peak_index]
                difference = np.abs(freq_ref[t] - nearest_peak)
                if difference <= 3*bins or np.isclose(difference, 3*bins):
                    rough_peak_refined[rough_peak_index].append(freq_ref[t])
            for e in range(len(rough_peak_refined)):
                refined_results.append({'short_fft_time':short_mid_time[f], 'short_fft_freq':rough_list[e], 'long_fft_freq':rough_peak_refined[e], 'long_fft_time':long_time})
    return refined_results

def track_indexing(peak_magnitudes, peak_frequency, short_mid_time):
    indexed_windows=[]
    for t in range(len(short_mid_time)):
        track_info=[]
        for j in range(len(peak_magnitudes[t])):
            track_info.append({'ID': None, 'time': short_mid_time[t], 'frequency': peak_frequency[t][j], 'strength': peak_magnitudes[t][j], 'status': 'CANDIDATE', 'detected': 1, 'miss':0, 'long_fft_candidate':[], 'long_fft_time':None, 'snr' : None, 'bandwidth':None})
        indexed_windows.append(track_info)
    return indexed_windows

def snr_bandwidth(indexed_windows, short_magnitude, short_frequency):
    for i in range(len(indexed_windows)):
        for z in range(len(indexed_windows[i])):
            mag_collection = []
            closest_bin_index = np.argmin(np.abs(indexed_windows[i][z]['frequency'] - short_frequency))
            if closest_bin_index >= 3:
                lower_bin_mag = short_magnitude[i][closest_bin_index-3:closest_bin_index]
                for k in range(len(lower_bin_mag)):
                    mag_collection.append(lower_bin_mag[k])
            if len(short_frequency) >= closest_bin_index + 4:
                higher_bin_mag = short_magnitude[i][closest_bin_index+1:closest_bin_index+4]
                for q in range(len(higher_bin_mag)):
                    mag_collection.append(higher_bin_mag[q])
            if len(mag_collection) > 0:
                noise_median = np.median(mag_collection)
                if noise_median != 0:
                    snr = short_magnitude[i][closest_bin_index]/noise_median
                else:
                    snr = None
            else:
                snr = None
            current_mag_window = short_magnitude[i]
            mag_peak = current_mag_window[closest_bin_index]
            cutoff_mag = mag_peak * 0.707
            lower_index = None
            higher_index = None
            for t in range(closest_bin_index - 1, -1, -1):
                if current_mag_window[t] < cutoff_mag:
                    lower_index = t
                    break
            for j in range(closest_bin_index + 1, len(current_mag_window)):
                if current_mag_window[j] < cutoff_mag:
                    higher_index = j
                    break
            if lower_index == None or higher_index == None:
                bandwidth = None
            else:
                bandwidth = short_frequency[higher_index] - short_frequency[lower_index]
            indexed_windows[i][z]['snr'] = snr
            indexed_windows[i][z]['bandwidth'] = bandwidth
    return indexed_windows


def track_comparison(indexed_windows, short_frequency, short_mid_time, refined_results, existing_completed_track_history, existing_lost, existing_terminated, existing_id_counter):
    initialized = False
    bins = short_frequency[1]-short_frequency[0]
    lost_timeout = 8
    for z in range(len(indexed_windows)):
        for y in range(len(indexed_windows[z])):
            for x in range(len(refined_results)):
                each_dict=refined_results[x]
                time=each_dict['short_fft_time']
                rough_freq=each_dict['short_fft_freq']
                refined_freq=each_dict['long_fft_freq']
                if indexed_windows[z][y]['time']==time and indexed_windows[z][y]['frequency']==rough_freq:
                    indexed_windows[z][y]['long_fft_candidate']=refined_freq
                    indexed_windows[z][y]['long_fft_time']=each_dict['long_fft_time']
                    break
    if len(existing_completed_track_history) == 0:
        all_id = []
        track_index = None
        for g in range(len(indexed_windows)):
            if len(indexed_windows[g]) > 0:
                track_index = g
                for n in range(len(indexed_windows[track_index])):
                   indexed_windows[track_index][n]['ID']='{:02d}'.format(n+1)
                break
        if track_index == None:
            return existing_completed_track_history, existing_lost, existing_terminated, existing_id_counter
        for m in range(len(indexed_windows[track_index])):
            all_id.append(int(indexed_windows[track_index][m]['ID']))
        existing_id_counter=np.max(all_id)
        existing_completed_track_history = copy.deepcopy([indexed_windows[track_index]])
        initialized = True
    if initialized == True:
        start_index = track_index + 1
    else:
        start_index = 0
    for i in range(start_index, len(indexed_windows)):
        old_track_info = copy.deepcopy(existing_completed_track_history[-1])
        track_info = indexed_windows[i]
        used_ID=[]
        for a in range(len(track_info)):
            match=False
            new_each=track_info[a]
            difference=[]
            for b in range(len(old_track_info)):
                old_each=old_track_info[b]
                if old_each['ID'] in used_ID:
                    used=np.inf
                    difference.append((used))
                else:
                    difference.append(abs(new_each['frequency']-old_each['frequency']))
            if len(difference)>0 and (difference[np.argmin(difference)]<=bins*1 or np.isclose(difference[np.argmin(difference)], bins*1) == True):
                min_index=np.argmin(difference)
                used_ID.append(old_track_info[min_index]['ID'])
                new_each['ID']=old_track_info[min_index]['ID']
                new_each['detected']=old_track_info[min_index]['detected']+1
                new_each['miss']=0
                if new_each['detected']>=2:
                    new_each['status']='ACTIVE'
                    old_track_info[min_index]['status']='ACTIVE'
                    new_each['miss']=0
                match=True
            if match==False and len(existing_lost)>0:
                lost_diff=[]
                lost_time=[]
                for l in range(len(existing_lost)):
                    match=False
                    each_lost=existing_lost[l]
                    lost_diff.append(np.abs(each_lost['frequency']-new_each['frequency']))
                    lost_time.append(np.abs(each_lost['time']-new_each['time']))
                lost_index=np.argmin(lost_diff)
                if (lost_diff[lost_index]<=1*bins or np.isclose(lost_diff[lost_index], 1*bins) == True) and lost_time[lost_index] < lost_timeout:
                    match=True
                    new_each['ID']=existing_lost[lost_index]['ID']
                    new_each['miss']=0
                    new_each['status']='ACTIVE'
                    new_each['detected']=existing_lost[lost_index]['detected']+1
                    existing_lost.remove(existing_lost[lost_index])
                    used_ID.append(new_each['ID'])
                elif match==False:
                    existing_id_counter=existing_id_counter+1
                    new_each['ID']='{:02d}'.format(existing_id_counter)
                    new_each['miss']=0
                    new_each['status']='CANDIDATE'
            elif match==False:
                existing_id_counter=existing_id_counter+1
                new_each['ID']='{:02d}'.format(existing_id_counter)
                new_each['miss']=0
                new_each['status']='CANDIDATE'
        for k in range(len(existing_lost)):
            time_diff=np.abs(existing_lost[k]['time']-short_mid_time[i])
            if time_diff >= lost_timeout:
                existing_lost[k]['status']='TERMINATED'
                existing_terminated.append(existing_lost[k])
        for c in range(len(old_track_info)):
            match=False
            old_each=old_track_info[c]
            if old_each['ID'] in used_ID:
                match=True
            if match==False:
                old_each['miss']+=1
                if old_each['detected']>=2 and old_each['miss']<=2:
                    old_each['status']='COASTING'
                    track_info.append(old_each)
                elif old_each['detected']>=2 and old_each['miss']>=3:
                    old_each['status']='LOST'
                    existing_lost.append(old_each)
        for s in range(len(existing_terminated)):
            if existing_terminated[s] in existing_lost:
                existing_lost.remove(existing_terminated[s])
        existing_completed_track_history.append(copy.deepcopy(track_info))
    return existing_completed_track_history, existing_lost, existing_terminated, existing_id_counter

def refined_collection(new_track_history, refined_history_archive):
    refined_history = {}
    new_refined_history = {}
    for z in range(len(new_track_history)):
        for y in range(len(new_track_history[z])):
            ind_ID = new_track_history[z][y]['ID']
            if ind_ID not in refined_history_archive:
                evidence = []
                long_time_used = set()
                refined_history_archive[ind_ID] = {'evidence':evidence, 'long_time_used':long_time_used}
            evidence = refined_history_archive[ind_ID]['evidence']
            long_time_used = refined_history_archive[ind_ID]['long_time_used']
            if new_track_history[z][y]['long_fft_time'] not in long_time_used and new_track_history[z][y]['long_fft_time'] is not None:
                new_evidence = {'time':new_track_history[z][y]['time'], 'long_fft_candidate':new_track_history[z][y]['long_fft_candidate'], 'long_fft_time':new_track_history[z][y]['long_fft_time']}
                evidence.append(new_evidence)
                long_time_used.add(new_track_history[z][y]['long_fft_time'])
                if ind_ID not in new_refined_history:
                    new_refined_history[ind_ID] = []
                new_refined_history[ind_ID].append(new_evidence)
    for ID in refined_history_archive.keys():
        refined_history[ID] = refined_history_archive[ID]['evidence']
    return refined_history, new_refined_history

def long_grouper(new_refined_history, refined_history, grouped_refined_archive):
    for i in refined_history.keys():
        if i not in grouped_refined_archive:
            grouped_refined_archive[i] = []
    for j in grouped_refined_archive.keys():
        for group in grouped_refined_archive[j]:
            group['new_time_set'].clear()
    for ID in new_refined_history.keys():
        groups = grouped_refined_archive[ID]
        for each_evidence in new_refined_history[ID]:
            for cand_freq in each_evidence['long_fft_candidate']:
                match = False
                for group in groups:
                    current_avg = group['frequency_sum']/group['count']
                    closeness=np.abs(cand_freq - current_avg)
                    if closeness <= 0.10:
                        group['points'].append({'frequency':cand_freq, 'long_time':each_evidence['long_fft_time']})
                        group['frequency_sum'] += cand_freq
                        group['count'] += 1
                        group['time_set'].add(each_evidence['long_fft_time'])
                        group['new_time_set'].add(each_evidence['long_fft_time'])
                        match=True
                        break
                if match == False:
                    group = {'points':[{'frequency':cand_freq, 'long_time':each_evidence['long_fft_time']}], 'frequency_sum':cand_freq, 'count':1, 'time_set':{each_evidence['long_fft_time']}, 'new_time_set':{each_evidence['long_fft_time']}}
                    groups.append(group)
    return

def persistency_analyzer(grouped_refined_archive):
    analysis_persistency = {}
    for i in grouped_refined_archive.keys():
        groups=[]
        for j in range(len(grouped_refined_archive[i])):
            frequency_average = grouped_refined_archive[i][j]['frequency_sum']/grouped_refined_archive[i][j]['count']
            entry_count = grouped_refined_archive[i][j]['count']
            each_group = {'first_long_time':grouped_refined_archive[i][j]['points'][0]['long_time'], 'last_long_time':grouped_refined_archive[i][j]['points'][-1]['long_time'], 'time_span':grouped_refined_archive[i][j]['points'][-1]['long_time'] - grouped_refined_archive[i][j]['points'][0]['long_time'], 'frequency_average':frequency_average, 'entry_count':entry_count}
            groups.append(each_group)
        analysis_persistency[i] = groups
    return analysis_persistency

def same_window(grouped_refined_archive, same_window_archive):
    collection_same_window={}
    for i in grouped_refined_archive.keys():
        if i not in same_window_archive:
            same_window_archive[i] = {}
        groups = grouped_refined_archive[i]
        pair_results = []
        for q in range(len(groups)):
            for r in range(q+1, len(groups)):
                pair_identity = (q, r)
                if pair_identity not in same_window_archive[i]:
                    same_window_archive[i][pair_identity] = {'group_1_index':q, 'group_2_index':r, 'share_time':[], 'share_time_set':set()}
                for z in groups[q]['new_time_set']:
                    if z in groups[r]['time_set'] and z not in same_window_archive[i][pair_identity]['share_time_set']:
                        same_window_archive[i][pair_identity]['share_time'].append(z)
                        same_window_archive[i][pair_identity]['share_time_set'].add(z)
                for y in groups[r]['new_time_set']:
                    if y in groups[q]['time_set'] and y not in same_window_archive[i][pair_identity]['share_time_set']:
                        same_window_archive[i][pair_identity]['share_time'].append(y)
                        same_window_archive[i][pair_identity]['share_time_set'].add(y)      
                pair_results.append({'group_1_index':q, 'group_2_index':r, 'shared_time':same_window_archive[i][pair_identity]['share_time'], 'shared_count':len(same_window_archive[i][pair_identity]['share_time_set'])})           
        collection_same_window[i] = pair_results
    return collection_same_window

def refined_comparison(analysis_persistency, collection_same_window):
    comparison_pair_info={}
    for i in collection_same_window.keys():
        pairs=[]
        for j in range(len(collection_same_window[i])):
            group_1_index=collection_same_window[i][j]['group_1_index']
            group_2_index=collection_same_window[i][j]['group_2_index']
            shared_count=collection_same_window[i][j]['shared_count']
            shares=False
            if shared_count>0:
                shares=True
            group_1_freq=analysis_persistency[i][group_1_index]['frequency_average']
            group_2_freq=analysis_persistency[i][group_2_index]['frequency_average']
            frequency_diff=np.abs(group_1_freq - group_2_freq)
            each_info={'group_1_index':group_1_index, 'group_1_freq':group_1_freq, 'group_2_index':group_2_index, 'group_2_freq':group_2_freq, 'freq_diff':frequency_diff, 'shares_window':shares, 'shared_count':shared_count}
            pairs.append(each_info)
        comparison_pair_info[i]=pairs
    return comparison_pair_info

def refined_decider_prep(analysis_persistency, collection_same_window):
    prep_info={}
    for i in analysis_persistency.keys():
        collect_info=[]
        for j in range(len(analysis_persistency[i])):
                group_avg=analysis_persistency[i][j]['frequency_average']
                group_count=analysis_persistency[i][j]['entry_count']
                group_time_span=analysis_persistency[i][j]['time_span']
                shares_window=False
                for k in range(len(collection_same_window[i])):
                    if (j==collection_same_window[i][k]['group_1_index'] or j==collection_same_window[i][k]['group_2_index']) and collection_same_window[i][k]['shared_count']>0:
                        shares_window=True
                group_info={'frequency_average':group_avg, 'entry_count':group_count, 'time_span':group_time_span, 'shares_window':shares_window}
                collect_info.append(group_info)
        prep_info[i]=collect_info
    return prep_info          

def valley_analyzer(comparison_pair_info, same_window_archive, long_magnitude, long_frequency, long_mid_time):
    valley_analyzed = {}
    for i in comparison_pair_info.keys():
        info = []
        for j in range(len(comparison_pair_info[i])):
            if comparison_pair_info[i][j]['shares_window'] == True:
                group_1_index = comparison_pair_info[i][j]['group_1_index']
                group_2_index = comparison_pair_info[i][j]['group_2_index']
                pair_identity = (group_1_index, group_2_index)
                share_time_set = same_window_archive[i][pair_identity]['share_time_set']
                for time_index in range(len(long_mid_time)):
                    if long_mid_time[time_index] in share_time_set:
                        order=[]
                        mag_window = long_magnitude[time_index]
                        group_1_freq = comparison_pair_info[i][j]['group_1_freq']
                        group_2_freq = comparison_pair_info[i][j]['group_2_freq']
                        group_1_bin_index = np.argmin(np.abs(long_frequency - group_1_freq))
                        group_2_bin_index = np.argmin(np.abs(long_frequency - group_2_freq))
                        order.append(group_1_bin_index)
                        order.append(group_2_bin_index)
                        order = np.sort(order)
                        mags = []
                        mag_1 = mag_window[order[0]]
                        mag_2 = mag_window[order[1]]
                        mags.append(mag_1)
                        mags.append(mag_2)
                        mag_range = mag_window[order[0]+1:order[1]]
                        if len(mag_range) > 0:
                            valley = np.min(mag_range)
                            valley_ratio = valley/np.min(mags)
                        else:
                            valley_ratio = None
                        result = {'group_1_index':comparison_pair_info[i][j]['group_1_index'], 'group_2_index':comparison_pair_info[i][j]['group_2_index'], 'shared_time':long_mid_time[time_index], 'valley_ratio':valley_ratio}
                        info.append(result)
        valley_analyzed[i] = info
    return valley_analyzed

def valley_scoring(comparison_pair_info, valley_analyzed):
    valley_score = {}
    for i in valley_analyzed.keys():
        pair_summary = []
        for k in range(len(comparison_pair_info[i])):
            valley_ratios = []
            shared_times = []
            group_1_index = comparison_pair_info[i][k]['group_1_index']
            group_2_index = comparison_pair_info[i][k]['group_2_index']
            for j in range(len(valley_analyzed[i])):
                if valley_analyzed[i][j]['group_1_index'] == group_1_index and valley_analyzed[i][j]['group_2_index'] == group_2_index and valley_analyzed[i][j]['valley_ratio'] != None:
                    pair_measurements = {'group_1_index':group_1_index, 'group_2_index':group_2_index, 'shared_times':valley_analyzed[i][j]['shared_time'], 'valley_ratio':valley_analyzed[i][j]['valley_ratio']}
                    valley_ratios.append(pair_measurements['valley_ratio'])
                    shared_times.append(pair_measurements['shared_times'])
            if len(valley_ratios) > 0:
                valley_median = np.median(valley_ratios)
            else:
                valley_median = None
            measurement_count = len(shared_times)
            pair_summary_dict = {'group_1_index':group_1_index, 'group_2_index':group_2_index, 'valley_median':valley_median, 'measurement_count':measurement_count}
            pair_summary.append(pair_summary_dict)
        valley_score[i] = pair_summary
    return valley_score

def refined_decider(time, valley_score, comparison_pair_info, prep_info, long_frequency, min_entry_count=2, min_time_span_ratio = 0.5, min_bin_separation = 2.0, min_shared_count = 2, max_valley_ratio = 0.9 ):
    track_decision = {}     
    for i in prep_info.keys():
        group_decision = []
        for j in range(len(prep_info[i])):
            freq_average = prep_info[i][j]['frequency_average']
            group_entry_count = prep_info[i][j]['entry_count']
            group_time_span = prep_info[i][j]['time_span']
            decision = 'UNCERTAIN'
            if len(prep_info[i]) == 1 and group_time_span >= (time[-1] - time[0]) * min_time_span_ratio and group_entry_count >= min_entry_count:
                decision = 'INDIVIDUAL'
            for k in range(len(comparison_pair_info[i])):
                valley_ratio = None
                shared_count = comparison_pair_info[i][k]['shared_count']
                freq_diff = comparison_pair_info[i][k]['freq_diff']
                bin_diff = freq_diff/(long_frequency[1] - long_frequency[0])
                for z in range(len(valley_score[i])):
                    if comparison_pair_info[i][k]['group_1_index'] == valley_score[i][z]['group_1_index'] and comparison_pair_info[i][k]['group_2_index'] == valley_score[i][z]['group_2_index']:
                        valley_ratio = valley_score[i][z]['valley_median']
                if np.isclose(bin_diff, min_bin_separation) == True:
                    bin_diff = min_bin_separation
                if (j == comparison_pair_info[i][k]['group_1_index'] or j == comparison_pair_info[i][k]['group_2_index']) and group_time_span >= (time[-1] - time[0]) * min_time_span_ratio and group_entry_count >= min_entry_count and shared_count >= min_shared_count and bin_diff >= min_bin_separation and valley_ratio is not None and valley_ratio <= max_valley_ratio:
                    decision = 'INDIVIDUAL'
            freq_decision={'frequency':freq_average, 'decision':decision}
            group_decision.append(freq_decision)
        for q in range(len(group_decision)):
            if group_decision[q]['decision'] == 'UNCERTAIN':
                for r in range(len(comparison_pair_info[i])):
                    index_1 = comparison_pair_info[i][r]['group_1_index']
                    index_2 = comparison_pair_info[i][r]['group_2_index']
                    freq_sort=[]
                    if group_decision[index_1]['decision'] == 'INDIVIDUAL' and group_decision[index_2]['decision'] == 'INDIVIDUAL':
                        freq_sort.append(group_decision[index_1]['frequency'])
                        freq_sort.append(group_decision[index_2]['frequency'])
                        freq_sort=np.sort(freq_sort)
                        if group_decision[q]['frequency'] > freq_sort[0] and group_decision[q]['frequency'] < freq_sort[1]:
                            if comparison_pair_info[i][r]['shared_count'] >= min_shared_count:
                                decision = 'BLENDED'
                                group_decision[q]['decision']=decision
                                break
        track_decision[i] = group_decision
    return track_decision

def refined_display(track_decision, new_track_history, track_history_archive, lost, terminated):
    latest_state = {}
    display_summary = {}
    for track in track_history_archive.keys():
        latest_state[track] = {'latest_frequency':track_history_archive[track]['frequency_history'][-1], 'latest_status':track_history_archive[track]['status_history'][-1], 'latest_strength':track_history_archive[track]['strength_history'][-1]}
    for i in range(len(new_track_history)):
        for j in range(len(new_track_history[i])):
            new_ID = new_track_history[i][j]['ID']
            latest_state[new_ID] = {'latest_frequency':new_track_history[i][j]['frequency'], 'latest_strength':new_track_history[i][j]['strength'], 'latest_status':new_track_history[i][j]['status']}
    for ID in latest_state.keys():
        latest_frequency = latest_state[ID]['latest_frequency']
        latest_strength = latest_state[ID]['latest_strength']
        latest_status = latest_state[ID]['latest_status']
        blended = []
        individual = []
        uncertain = []
        if ID in track_decision:
            refined_components = track_decision[ID]
        else:
            refined_components = []
        for k in range(len(refined_components)):
            if refined_components[k]['decision'] == 'INDIVIDUAL':
                individual.append(refined_components[k]['frequency'])
            elif refined_components[k]['decision'] == 'BLENDED':
                blended.append(refined_components[k]['frequency'])
            elif refined_components[k]['decision'] == 'UNCERTAIN':
                uncertain.append(refined_components[k]['frequency'])
        for y in range(len(lost)):
            if ID == lost[y]['ID']:
                latest_status = 'LOST'
        for z in range(len(terminated)):
            if ID == terminated[z]['ID']:
                latest_status = 'TERMINATED'
        summary = {'track':ID, 'rough_frequency':latest_frequency, 'strength':latest_strength, 'status':latest_status, 'confirmed':individual, 'blended':blended, 'uncertain':uncertain}
        display_summary[ID] = summary
    return display_summary

def history_realtime(new_track_history, display_summary, track_history_archive):
    for i in range(len(new_track_history)):
        for j in range(len(new_track_history[i])):
            track = new_track_history[i][j]['ID']
            if track not in track_history_archive:
                track_history_archive[track] = {'time_history':[], 'strength_history':[], 'frequency_history':[], 'status_history':[], 'snr_history':[], 'bandwidth_history':[], 'instant_freq_drift_rate':[], 'instant_strength_change_rate':[], 'frequency_stats':{'count':0, 'mean':0, 'M2':0}, 'strength_stats':{'count':0, 'mean':0, 'M2':0}, 'active_count':0, 'active_time_history':[], 'active_frequency_history':[]}
            track_history_archive[track]['time_history'].append(new_track_history[i][j]['time'])
            track_history_archive[track]['strength_history'].append(new_track_history[i][j]['strength'])
            track_history_archive[track]['frequency_history'].append(new_track_history[i][j]['frequency'])
            track_history_archive[track]['status_history'].append(new_track_history[i][j]['status'])
            track_history_archive[track]['snr_history'].append(new_track_history[i][j]['snr'])
            track_history_archive[track]['bandwidth_history'].append(new_track_history[i][j]['bandwidth'])
            new_freq = new_track_history[i][j]['frequency']
            track_history_archive[track]['frequency_stats']['count'] += 1
            delta = new_freq - track_history_archive[track]['frequency_stats']['mean']
            track_history_archive[track]['frequency_stats']['mean'] += delta/track_history_archive[track]['frequency_stats']['count']
            delta_2 = new_freq - track_history_archive[track]['frequency_stats']['mean']
            track_history_archive[track]['frequency_stats']['M2'] += delta * delta_2
            new_strength = new_track_history[i][j]['strength']
            track_history_archive[track]['strength_stats']['count'] += 1
            delta = new_strength - track_history_archive[track]['strength_stats']['mean']
            track_history_archive[track]['strength_stats']['mean'] += delta / track_history_archive[track]['strength_stats']['count']
            delta_2 = new_strength - track_history_archive[track]['strength_stats']['mean']
            track_history_archive[track]['strength_stats']['M2'] += delta * delta_2
            if new_track_history[i][j]['status'] == 'ACTIVE':
                track_history_archive[track]['active_count'] += 1
                track_history_archive[track]['active_time_history'].append(new_track_history[i][j]['time'])
                track_history_archive[track]['active_frequency_history'].append(new_track_history[i][j]['frequency'])
    for ID in display_summary.keys():
        if ID in track_history_archive:
            display_summary[ID]['time_history'] = track_history_archive[ID]['time_history']
            display_summary[ID]['strength_history'] = track_history_archive[ID]['strength_history']
            display_summary[ID]['frequency_history'] = track_history_archive[ID]['frequency_history']
            display_summary[ID]['status_history'] = track_history_archive[ID]['status_history']
            display_summary[ID]['snr_history'] = track_history_archive[ID]['snr_history']
            display_summary[ID]['bandwidth_history'] = track_history_archive[ID]['bandwidth_history']
            display_summary[ID]['latest_snr'] = track_history_archive[ID]['snr_history'][-1]
            display_summary[ID]['latest_bandwidth'] = track_history_archive[ID]['bandwidth_history'][-1]
    return display_summary

def frequency_drift(display_summary, track_history_archive):
    for i in display_summary.keys():
        frequency_his = display_summary[i]['frequency_history']
        time_his = display_summary[i]['time_history']
        inst_drift_his = track_history_archive[i]['instant_freq_drift_rate']
        drift_val = len(frequency_his) - 1
        while drift_val > len(inst_drift_his):
            prev_ind = len(inst_drift_his)
            next_ind = prev_ind + 1
            dt = time_his[next_ind] - time_his[prev_ind]
            if dt != 0:
                inst_drift_rate = (frequency_his[next_ind] - frequency_his[prev_ind]) / dt
            else:
                inst_drift_rate = None
            inst_drift_his.append(inst_drift_rate)
        if len(frequency_his) >= 2 and time_his[-1] != time_his[0]:
            net = (frequency_his[-1]-frequency_his[0])/(time_his[-1]-time_his[0])
        else:
            net = None
        display_summary[i]['instant_freq_drift_rate'] = inst_drift_his
        display_summary[i]['net_freq_drift_rate'] = net
    return display_summary

def strength_trend(display_summary, track_history_archive):
    for i in display_summary.keys():
        strength_his = display_summary[i]['strength_history']
        time_his = display_summary[i]['time_history']
        inst_strength_his = track_history_archive[i]['instant_strength_change_rate']
        trend_val = len(strength_his) - 1
        while trend_val > len(inst_strength_his):
            prev_ind = len(inst_strength_his)
            next_ind = prev_ind + 1
            dt = time_his[next_ind] - time_his[prev_ind]
            if dt != 0:
                inst_strength_change = (strength_his[next_ind] - strength_his[prev_ind]) / dt
            else:
                inst_strength_change = None
            inst_strength_his.append(inst_strength_change)
        if len(strength_his) >= 2 and time_his[-1] != time_his[0]:
            net = (strength_his[-1] - strength_his[0]) / (time_his[-1] - time_his[0])
        else:
            net = None
        display_summary[i]['instant_strength_change_rate'] = inst_strength_his
        display_summary[i]['net_strength_change_rate'] = net
    return display_summary

def stability_analyzer(display_summary, track_history_archive):
    for i in display_summary.keys():
        freq_stats = track_history_archive[i]['frequency_stats']
        str_stats = track_history_archive[i]['strength_stats']
        if freq_stats['count'] >= 2 and str_stats['count'] >= 2: 
            freq_std = (freq_stats['M2']/freq_stats['count']) ** 0.5
            str_std = (str_stats['M2']/str_stats['count']) ** 0.5
        else:
            freq_std = None
            str_std = None
        display_summary[i]['frequency_std'] = freq_std
        display_summary[i]['strength_std'] = str_std
    return display_summary

def confidence_score(display_summary, track_history_archive):
    for i in display_summary.keys():
        latest_snr = display_summary[i]['latest_snr']
        frequency_std = display_summary[i]['frequency_std']
        strength_std = display_summary[i]['strength_std']
        latest_bandwidth = display_summary[i]['latest_bandwidth']
        status = display_summary[i]['status']
        if latest_snr is None:
            snr_score = None
        elif latest_snr <= 1:
            snr_score = 0
        elif latest_snr >= 25:
            snr_score = 1
        else:
            snr_score = (latest_snr - 1)/(25-1)
        if frequency_std is None:
            frequency_stability = None
        elif frequency_std >= 1:
            frequency_stability = 0
        elif frequency_std <= 0:
            frequency_stability = 1
        else:
            frequency_stability = 1 - frequency_std
        if latest_bandwidth is None:
            bandwidth_score = None
        elif latest_bandwidth <= 2:
            bandwidth_score = 1
        elif latest_bandwidth >= 5:
            bandwidth_score = 0
        else:
            bandwidth_score = 1 - ((latest_bandwidth - 2)/(5-2))
        average_strength = track_history_archive[i]['strength_stats']['mean']
        relative_variation = None
        if average_strength != 0 and strength_std is not None:
            relative_variation = strength_std / average_strength
        if relative_variation is None:
            strength_stability = None
        elif relative_variation <= 0:
            strength_stability = 1
        elif relative_variation >= 0.2:
            strength_stability = 0
        else:
            strength_stability = 1 - relative_variation/0.2
        if status == 'ACTIVE':
            status_score = 1
        elif status == 'COASTING':
            status_score = 0.5
        elif status == 'CANDIDATE':
            status_score = 0.25
        elif status == 'LOST' or status == 'TERMINATED':
            status_score = 0
        else:
            status_score = None
        score_storage = {'snr_score':snr_score, 'frequency_stability':frequency_stability, 'bandwidth_score':bandwidth_score, 'strength_stability':strength_stability, 'status_score':status_score}
        score_weight = {'snr_score':0.35, 'frequency_stability':0.25, 'bandwidth_score':0.2, 'strength_stability':0.1, 'status_score':0.1}
        top = []
        bottom = []
        confidence_score_track = None
        for j in score_storage.keys():
            if score_storage[j] is not None:
                top.append(score_storage[j] * score_weight[j])
                bottom.append(score_weight[j])
        if len(top) > 0 and len(bottom) > 0:
            confidence_score_track = np.sum(top)/np.sum(bottom)
        display_summary[i]['confidence_score'] = confidence_score_track
    return display_summary

def active_collection(track_history_archive, time_range):
    active_time=[]
    active_freq=[]
    active_id=[]
    visible_start = time_range[0]
    visible_end = time_range[-1]
    for ID in track_history_archive.keys():
        active_time_history = track_history_archive[ID]['active_time_history']
        active_freq_history = track_history_archive[ID]['active_frequency_history']
        start_index = bisect_left(active_time_history, visible_start)
        end_index = bisect_right(active_time_history, visible_end)
        visible_time = active_time_history[start_index:end_index]
        visible_freq = active_freq_history[start_index:end_index]
        active_time.extend(visible_time)
        active_freq.extend(visible_freq)
        active_id.extend([ID] * len(visible_time))
    return active_time, active_freq, active_id

def accepted_track(display_summary, track_history_archive):
    accepted_ID = []
    for ID in display_summary.keys():
        if track_history_archive[ID]['active_count'] >= 2:
            accepted_ID.append(ID)
    return accepted_ID

def reduce_spectrogram_display(mag, freq, display_min, display_max, max_rows):
    # I'm reducing spectrogram rows with max pooling so strong frequency peaks remain visible
    spectrogram_matrix = np.array(mag)
    spectrogram_matrix = spectrogram_matrix.T
    visible_frequency_mask = (freq >= display_min) & (freq <= display_max)
    visible_index = np.where(visible_frequency_mask)[0]
    if len(visible_index) == 0:
        spectrogram_min = freq[0]
        spectrogram_max = freq[-1]
        return spectrogram_matrix, spectrogram_min, spectrogram_max
    start_index = visible_index[0]
    end_index = visible_index[-1] + 1
    visible_matrix = spectrogram_matrix[start_index:end_index]
    visible_frequency = freq[start_index:end_index]
    spectrogram_min = visible_frequency[0]
    spectrogram_max = visible_frequency[-1]
    if len(visible_frequency) <= max_rows:
        return visible_matrix, spectrogram_min, spectrogram_max
    bucket_size = len(visible_frequency) / max_rows
    bucket_size = int(np.ceil(bucket_size))
    display_rows = []
    for start_row in range(0, len(visible_frequency), bucket_size):
        end_row = start_row + bucket_size
        if end_row > len(visible_frequency):
            end_row = len(visible_frequency)
        frequency_bucket = visible_matrix[start_row:end_row]
        strongest_row = np.max(frequency_bucket, axis = 0)
        display_rows.append(strongest_row)
    display_matrix = np.array(display_rows)
    return display_matrix, spectrogram_min, spectrogram_max

def plotting_spectrogram(time, ax, display_min, display_max, mag, freq, mid_time, accepted_ID, active_time, active_freq, ID, grouped_refined_archive, existing_spectrogram = None, existing_colorbar = None):
    color_map = ['#01070B', '#03151B', '#06313A', '#075866', '#008C99', '#00B8C2', '#00DADD', '#19F2EF', '#72FFFA', '#C8FFFC']
    blacksite_map = LinearSegmentedColormap.from_list('blacksite', color_map)
    cyan = '#39f6ff'
    text = '#00e5ff'
    display_row_limit = int(ax.bbox.height)
    if display_row_limit < 250:
        display_row_limit = 250
    spectrogram_matrix, spectrogram_min, spectrogram_max = reduce_spectrogram_display(mag, freq, display_min, display_max, display_row_limit)
    db = 20*(np.log10(1e-12 + spectrogram_matrix))
    if existing_spectrogram is None:
        spectrogram = ax.imshow(db, vmin = -95, vmax = 20, extent=(time[0], time[-1], spectrogram_min, spectrogram_max), aspect = 'auto', origin='lower', cmap = blacksite_map)
    else:
        spectrogram = existing_spectrogram
        spectrogram.set_data(db)
        spectrogram.set_extent((time[0], time[-1], spectrogram_min, spectrogram_max))
    if existing_colorbar is None:
        colorbar = ax.figure.colorbar(spectrogram, ax=ax)
        colorbar.set_label('Amplitude (dB)', color = text)
        colorbar.ax.tick_params(color = text, labelcolor = text)
    else:
        colorbar = existing_colorbar
    ax.set_ylim(display_min, display_max)
    ax.set_xticks(mid_time[::2])
    ax.set_xlabel('Time (s)', color = text)
    ax.set_title('SPECTROGRAM', fontsize = 11, color = cyan)
    ax.set_ylabel('Frequency (Hz)', color = text)
    ax.tick_params(color = text, labelcolor = text)
    each_ID=np.unique(ID)
    track_ID = []
    refined_marker = []
    active_line = []
    for j in range(len(each_ID)):
        each_time = []
        each_freq = []
        refined_time = []
        refined_freq = []
        if each_ID[j] in accepted_ID:
            for group in grouped_refined_archive[each_ID[j]]:
                points = group['points']
                start_index = bisect_left(points, time[0], key=lambda point: point['long_time'])
                end_index = bisect_right(points, time[-1], key=lambda point: point['long_time'])
                visible_points = points[start_index:end_index]
                for point in visible_points:
                    refined_time.append(point['long_time'])
                    refined_freq.append(point['frequency'])
            for k in range(len(ID)):
                if each_ID[j]==ID[k]:
                    each_time.append(active_time[k])
                    each_freq.append(active_freq[k])
            ref_marker = ax.plot(refined_time, refined_freq, '#00AFC4', marker = 'o', markerfacecolor = 'none', linestyle = 'none')
            ref_marker[0].set_animated(True)
            refined_marker.append(ref_marker[0])
            if len(each_time)>0:
                if display_min <= each_freq[-1] <= display_max:
                    ID_text = ax.text(each_time[-1], each_freq[-1], each_ID[j], color = '#00AFC4')
                    ID_text.set_animated(True)
                    track_ID.append(ID_text)
            mark = ax.plot(each_time, each_freq, '#00AFC4', marker = 'o')
            mark[0].set_animated(True)
            active_line.append(mark[0])
    return spectrogram, colorbar, active_line, track_ID, refined_marker

def export_track(display_summary, file_path):
    headers = ['track_id', 'time', 'status', 'rough_frequency', 'strength', 'snr', 'bandwidth', 'frequency_drift', 'strength_trend']
    with open(file_path, 'w', newline = '', encoding = 'utf-8') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(headers)
        for ID in display_summary.keys():
            for i in range(len(display_summary[ID]['time_history'])):
                time = display_summary[ID]['time_history'][i]
                rough_frequency_history = display_summary[ID]['frequency_history'][i]
                strength_history = display_summary[ID]['strength_history'][i]
                status_history = display_summary[ID]['status_history'][i]
                snr_history = display_summary[ID]['snr_history'][i]
                bandwidth_history = display_summary[ID]['bandwidth_history'][i]
                if i == 0:
                    frequency_drift = 'N/A'
                    instant_strength_change_rate = 'N/A'
                else:
                    frequency_drift = display_summary[ID]['instant_freq_drift_rate'][i-1]
                    instant_strength_change_rate = display_summary[ID]['instant_strength_change_rate'][i-1]
                writer.writerow([ID, time, status_history, rough_frequency_history, strength_history, snr_history, bandwidth_history, frequency_drift, instant_strength_change_rate])
    return

def export_summary(display_summary, file_path):
    headers = ['track_id', 'final_status', 'latest_rough_frequency', 'latest_strength', 'confirmed_refined', 'blended_refined', 'uncertain_refined', 'net_frequency_drift', 'net_strength_trend', 'frequency_std', 'strength_std', 'latest_snr', 'latest_bandwidth', 'confidence']
    with open(file_path, 'w', newline = '', encoding = 'utf-8') as csv_summary:
        writer = csv.writer(csv_summary)
        writer.writerow(headers)
        for ID in display_summary.keys():
            final_status = display_summary[ID]['status']
            latest_rough_frequency = display_summary[ID]['rough_frequency']
            latest_strength = display_summary[ID]['strength']
            if len(display_summary[ID]['confirmed']) > 0:
                confirmed_text = []
                for i in range(len(display_summary[ID]['confirmed'])):
                    confirmed = str(display_summary[ID]['confirmed'][i])
                    confirmed_text.append(confirmed)
                confirmed_refined = '; '.join(confirmed_text)
            else:
                confirmed_refined = ''
            if len(display_summary[ID]['blended']) > 0:
                blended_text = []
                for i in range(len(display_summary[ID]['blended'])):
                    blended = str(display_summary[ID]['blended'][i])
                    blended_text.append(blended)
                blended_refined = '; '.join(blended_text)
            else:
                blended_refined = ''
            if len(display_summary[ID]['uncertain']) > 0:
                uncertain_text = []
                for i in range(len(display_summary[ID]['uncertain'])):
                    uncertain = str(display_summary[ID]['uncertain'][i])
                    uncertain_text.append(uncertain)
                uncertain_refined = '; '.join(uncertain_text)
            else:
                uncertain_refined = ''
            net_frequency_drift = display_summary[ID]['net_freq_drift_rate']
            net_strength_trend = display_summary[ID]['net_strength_change_rate']
            frequency_std = display_summary[ID]['frequency_std']
            strength_std = display_summary[ID]['strength_std']
            latest_snr = display_summary[ID]['latest_snr']
            latest_bandwidth = display_summary[ID]['latest_bandwidth']
            confidence = display_summary[ID]['confidence_score']
            writer.writerow([ID, final_status, latest_rough_frequency, latest_strength, confirmed_refined, blended_refined, uncertain_refined, net_frequency_drift, net_strength_trend, frequency_std, strength_std, latest_snr, latest_bandwidth, confidence])
    return

def compact_number(value, axis = False):
    value = float(value)
    absolute_value = abs(value)
    if axis == True:
        if absolute_value >= 1000000:
            display_value = value / 1000000
            return '{:.1f}M'.format(display_value)
        elif absolute_value >= 1000:
            display_value = value / 1000
            return '{:.1f}k'.format(display_value)
    else:
        if absolute_value >= 1000000:
            display_value = value / 1000000
            return '{:.2f}M'.format(display_value)
        elif absolute_value >= 10000:
            display_value = value / 1000
            return '{:.1f}k'.format(display_value)
    if value.is_integer() == True:
        return '{}'.format(int(value))
    else:
        return '{:.2f}'.format(value)

def compact_tick(value, position):
    return compact_number(value, axis = True)

def dashboard(signal, time, file_path, on_close = None, display_min = 0, display_max = 20):
    source_name = os.path.splitext(os.path.basename(file_path))[0]
    sample_rate = 1/np.median(np.diff(time))
    # Analysis timing is defined in seconds and sample size increase with input sample rate
    short_analysis_dur = 1.0
    long_analysis_dur = 4.0
    hop_dur = 0.5
    buffer_dur = 5.0
    short_analysis_sample = round(short_analysis_dur * sample_rate)
    long_analysis_sample = round(long_analysis_dur * sample_rate)
    hop_size = round(hop_dur * sample_rate)
    buffer_size = round(buffer_dur * sample_rate)
    live_index = [short_analysis_sample]
    live_step = hop_size
    timer_counter = [0]
    nyquist = 1/(2*(time[1] - time[0]))
    paused = [False]
    finished = [False]
    resize_pending = [False]
    existing_completed_track_history = []
    existing_lost = []
    existing_terminated = []
    existing_id_counter = 0
    track_history_archive = {}
    refined_history_archive = {}
    grouped_refined_archive = {}
    same_window_archive = {}
    latest_processed_index = [None]
    header_bbox = None
    header_background = None
    spectrogram_bbox = None
    spectrogram_background = None
    waveform_bbox = None
    waveform_background = None
    spectrum_background = None
    spectrum_bbox = None
    telemetry_bbox = None
    telemetry_background = None
    strength_history_bbox = None
    strength_history_background = None
    freq_history_bbox = None
    freq_history_background = None
    snr_history_bbox = None
    snr_history_background = None
    bandwidth_history_bbox = None
    bandwidth_history_background = None
    strength_history_click_background = None
    freq_history_click_background = None
    snr_history_click_background = None
    bandwidth_history_click_background = None
    freq_slider_background = None
    freq_slider_bbox = None
    def buffer_slicing(signal, time, buffer_size, live_index):
        start_sample = max(0, (live_index - buffer_size))
        end_sample = min(live_index, len(signal))
        signal_range = signal[start_sample : end_sample]
        time_range = time[start_sample : end_sample]
        return signal_range, time_range, start_sample
    def analyzing_buffer(signal_range, time_range, start_sample, window_size = short_analysis_sample, step = hop_size):    
        windows, short_mid_time, short_window_index = window_extract(signal_range, time_range, start_sample, window_size, step)
        short_magnitude, short_frequency, short_mid_time = window_fft(windows, short_mid_time, time_range)    
        peak_magnitudes, peak_frequency, short_mid_time = peak_detection(short_magnitude, short_frequency, short_mid_time)
        new_short_peak_frequency = []
        new_short_mid_time = []
        for i in range(len(short_window_index)):
            if latest_processed_index[0] == None or short_window_index[i] > latest_processed_index[0]:
                new_short_peak_frequency.append(peak_frequency[i])
                new_short_mid_time.append(short_mid_time[i])
        if len(signal_range) >= long_analysis_sample:    
            long_magnitude, long_frequency, long_mid_time = window_fft_high(signal_range, time_range, start_sample, long_analysis_sample, step)        
            refined_results = frequency_refining(new_short_peak_frequency, short_frequency, new_short_mid_time, long_magnitude, long_frequency, long_mid_time)    
        else:
            long_magnitude = []
            long_frequency = []
            long_mid_time = []
            refined_results = []
        indexed_windows = track_indexing(peak_magnitudes, peak_frequency, short_mid_time)
        indexed_windows = snr_bandwidth(indexed_windows, short_magnitude, short_frequency)
        return short_magnitude, short_frequency, short_mid_time, short_window_index, long_magnitude, long_frequency, long_mid_time, refined_results, indexed_windows
    def latest_data_filter(indexed_windows, short_mid_time, short_window_index, refined_results):
        # I'm processing only the short FFT windows that have not already been analyzed
        # This prevents the rolling buffer from repeatedly processing old detections which made it fail my soak test
        new_short_window_index = []
        new_indexed_windows = []
        new_short_mid_time = []
        new_refined_results = []
        if latest_processed_index[0] is None:
            for k in range(len(short_window_index)):
                new_short_window_index.append(short_window_index[k])
                new_indexed_windows.append(indexed_windows[k])
                new_short_mid_time.append(short_mid_time[k])
        else:
            for i in range(len(short_window_index)):
                if short_window_index[i] > latest_processed_index[0]:
                    new_short_window_index.append(short_window_index[i])
                    new_indexed_windows.append(indexed_windows[i])
                    new_short_mid_time.append(short_mid_time[i])
        if len(new_short_window_index) > 0:
            latest_processed_index[0] = new_short_window_index[-1]
        for j in range(len(refined_results)):
            for q in range(len(new_short_mid_time)):
                if refined_results[j]['short_fft_time'] == new_short_mid_time[q]:
                    new_refined_results.append(refined_results[j])
                    break
        return new_indexed_windows, new_short_mid_time, new_refined_results
    def buffer_processing():
        nonlocal existing_completed_track_history, existing_lost, existing_terminated, existing_id_counter
        signal_range, time_range, start_sample = buffer_slicing(signal, time, buffer_size, live_index[0])
        short_magnitude, short_frequency, short_mid_time, short_window_index, long_magnitude, long_frequency, long_mid_time, refined_results, indexed_windows = analyzing_buffer(signal_range, time_range, start_sample)
        new_indexed_windows, new_short_mid_time, new_refined_results = latest_data_filter(indexed_windows, short_mid_time, short_window_index, refined_results)
        window_count = len(existing_completed_track_history)
        existing_completed_track_history, existing_lost, existing_terminated, existing_id_counter = track_comparison(new_indexed_windows, short_frequency, new_short_mid_time, new_refined_results, existing_completed_track_history, existing_lost, existing_terminated, existing_id_counter)
        new_track_history = existing_completed_track_history[window_count:]
        refined_history, new_refined_history = refined_collection(new_track_history, refined_history_archive)
        long_grouper(new_refined_history, refined_history, grouped_refined_archive)
        analysis_persistency = persistency_analyzer(grouped_refined_archive)
        collection_same_window = same_window(grouped_refined_archive, same_window_archive)
        comparison_pair_info = refined_comparison(analysis_persistency, collection_same_window)
        prep_info = refined_decider_prep(analysis_persistency, collection_same_window)
        valley_analyzed = valley_analyzer(comparison_pair_info, same_window_archive, long_magnitude, long_frequency, long_mid_time)
        valley_score = valley_scoring(comparison_pair_info, valley_analyzed)
        track_decision = refined_decider(time_range, valley_score, comparison_pair_info, prep_info, long_frequency)
        display_summary = refined_display(track_decision, new_track_history, track_history_archive, existing_lost, existing_terminated)
        display_summary = history_realtime(new_track_history, display_summary, track_history_archive)
        display_summary = frequency_drift(display_summary, track_history_archive)
        display_summary = strength_trend(display_summary, track_history_archive)
        display_summary = stability_analyzer(display_summary, track_history_archive)
        display_summary = confidence_score(display_summary, track_history_archive)
        accepted_ID = accepted_track(display_summary, track_history_archive)
        active_time, active_freq, ID = active_collection(track_history_archive, time_range)
        return signal_range, time_range, short_magnitude, short_frequency, short_mid_time, long_magnitude, long_frequency, long_mid_time, existing_completed_track_history, display_summary, accepted_ID, active_time, active_freq, ID
    def live_update(live_index, live_step):
        live_index[0] += live_step
        live_index[0] = min(live_index[0], len(signal))
        signal_range, time_range, short_magnitude, short_frequency, short_mid_time, long_magnitude, long_frequency, long_mid_time, existing_completed_track_history, display_summary, accepted_ID, active_time, active_freq, ID = buffer_processing()
        return signal_range, time_range, short_magnitude, short_frequency, short_mid_time, long_magnitude, long_frequency, long_mid_time, existing_completed_track_history, display_summary, accepted_ID, active_time, active_freq, ID
    def spectrogram_refresh_display():
        nonlocal spectrogram, colorbar, active_line, track_ID, refined_marker
        spectrogram, colorbar, active_line, track_ID, refined_marker = spectrogram_update(spectrogram, colorbar, active_line, track_ID, refined_marker, time_range, ax_spectrogram, display_min, display_max, short_magnitude, short_frequency, short_mid_time, accepted_ID, active_time, active_freq, ID, grouped_refined_archive)
        fig.canvas.restore_region(spectrogram_background)
        ax_spectrogram.draw_artist(spectrogram)
        for lines in active_line:
            ax_spectrogram.draw_artist(lines)
        for texts in track_ID:
            ax_spectrogram.draw_artist(texts)
        for markers in refined_marker:
            ax_spectrogram.draw_artist(markers)
        ax_spectrogram.draw_artist(ax_spectrogram.xaxis)
        ax_spectrogram.draw_artist(ax_spectrogram.yaxis)
        fig.canvas.blit(spectrogram_bbox)
    def fast_refresh_display(refresh_spectrogram = True):
        selected_ID_update()
        waveform_update(ax_waveform, signal_range, time_range)
        fig.canvas.restore_region(waveform_background)
        ax_waveform.draw_artist(ax_waveform.xaxis)
        ax_waveform.draw_artist(waveform_line)
        fig.canvas.blit(waveform_bbox)
        spectrum_update(short_frequency, short_magnitude)
        fig.canvas.restore_region(spectrum_background)
        ax_spectrum.draw_artist(ax_spectrum.xaxis)
        ax_spectrum.draw_artist(spectrum_line)
        fig.canvas.blit(spectrum_bbox)
        if refresh_spectrogram == True:
            spectrogram_refresh_display()
    def dense_refresh_display():
        nonlocal strength_history_click_background, freq_history_click_background, snr_history_click_background, bandwidth_history_click_background
        selected_ID_update()
        draw_registry()
        ax_tracks.draw(fig.canvas.get_renderer())
        fig.canvas.blit(ax_tracks.bbox)
        draw_graphs()
        fig.canvas.restore_region(freq_history_background)
        ax_freq_history.draw_artist(ax_freq_history.xaxis)
        freq_history_click_background = fig.canvas.copy_from_bbox(freq_history_bbox)
        ax_freq_history.draw_artist(ax_freq_history.yaxis)
        ax_freq_history.draw_artist(freq_line)
        fig.canvas.blit(freq_history_bbox)
        fig.canvas.restore_region(strength_history_background)
        ax_strength_history.draw_artist(ax_strength_history.xaxis)
        strength_history_click_background = fig.canvas.copy_from_bbox(strength_history_bbox)
        ax_strength_history.draw_artist(ax_strength_history.yaxis)
        ax_strength_history.draw_artist(strength_line)
        fig.canvas.blit(strength_history_bbox)
        fig.canvas.restore_region(snr_history_background)
        ax_snr_history.draw_artist(ax_snr_history.xaxis)
        snr_history_click_background = fig.canvas.copy_from_bbox(snr_history_bbox)
        ax_snr_history.draw_artist(ax_snr_history.yaxis)
        ax_snr_history.draw_artist(snr_line)
        fig.canvas.blit(snr_history_bbox)
        fig.canvas.restore_region(bandwidth_history_background)
        ax_bandwidth_history.draw_artist(ax_bandwidth_history.xaxis)
        bandwidth_history_click_background = fig.canvas.copy_from_bbox(bandwidth_history_bbox)
        ax_bandwidth_history.draw_artist(ax_bandwidth_history.yaxis)
        ax_bandwidth_history.draw_artist(bw_line)
        fig.canvas.blit(bandwidth_history_bbox)
        draw_telemetry()
        fig.canvas.restore_region(telemetry_background)
        for t in telemetry_text:
            ax_telemetry.draw_artist(t)
        fig.canvas.blit(telemetry_bbox)
        draw_header()
        fig.canvas.restore_region(header_background)
        for header_object in header_text:
            ax_header.draw_artist(header_object)
        fig.canvas.blit(header_bbox)
        refresh_freq_slider()
    signal_range, time_range, short_magnitude, short_frequency, short_mid_time, long_magnitude, long_frequency, long_mid_time, existing_completed_track_history, display_summary, accepted_ID, active_time, active_freq, ID = buffer_processing()
    detected_start_freq = []
    for key in display_summary.keys():
        detected_start_freq.append(display_summary[key]['rough_frequency'])
    if nyquist < 20:
        display_min = 0
        display_max = nyquist
    elif len(detected_start_freq) == 0:
        display_min = 0
        display_max = 20
    else:
        detected_min = np.min(detected_start_freq)
        detected_max = np.max(detected_start_freq)
        detected_span = detected_max - detected_min
        display_padding = detected_span * 0.05
        if display_padding < 5:
            display_padding = 5
        lowest_det = max(0, detected_min - display_padding)
        highest_det = min(detected_max + display_padding, nyquist)
        if highest_det - lowest_det < 20:
            center = (lowest_det + highest_det) / 2
            lowest_det = center - 10
            highest_det = center + 10
            if lowest_det < 0:
                lowest_det = 0
                highest_det = 20
            elif highest_det > nyquist:
                highest_det = nyquist
                lowest_det = nyquist - 20
        display_min = lowest_det
        display_max = highest_det
    platform_status = 'ONLINE'
    platform_mode = 'LIVE'
    active_online_individual = '#B8FCFF'
    candidate_coasting_uncertain = '#FFB547'
    lost_terminated_warnings = '#FF5A4F'
    figure_bg = '#07111a'
    panel_bg = '#0b1a26'
    cyan = '#39f6ff'
    text = '#00e5ff'
    border = '#167f8f'
    text_border = '#167f8f'
    signal_cyan = '#46f9ff'
    fig = plt.figure(figsize = (18, 9))
    def close_window(event):
        if on_close is not None:
            on_close()
    fig.canvas.mpl_connect('close_event', close_window)
    manager = plt.get_current_fig_manager()
    starting_size = manager.window.size()
    manager.window.setMinimumSize(starting_size)
    fig.patch.set_facecolor(figure_bg)
    grid = fig.add_gridspec(4, 3, width_ratios = [4.5, 2, 2], height_ratios = [0.2, 2, 2, 2.5], hspace = 0.6)
    ax_spectrogram = fig.add_subplot(grid[1:3, 0:2])
    ax_spectrogram.patch.set_facecolor(panel_bg)
    ax_spectrogram.spines['top'].set_color(border)
    ax_spectrogram.spines['left'].set_color(border)
    ax_spectrogram.spines['right'].set_color(border)
    ax_spectrogram.spines['bottom'].set_color(border)
    ax_header = fig.add_subplot(grid[0, 0:3])
    ax_header.patch.set_facecolor(panel_bg)
    ax_waveform = fig.add_subplot(grid[1, 2])
    ax_waveform.patch.set_facecolor(panel_bg)
    ax_waveform.spines['top'].set_color(border)
    ax_waveform.spines['left'].set_color(border)
    ax_waveform.spines['right'].set_color(border)
    ax_waveform.spines['bottom'].set_color(border)
    ax_spectrum = fig.add_subplot(grid[2, 2])
    ax_spectrum.patch.set_facecolor(panel_bg)
    ax_spectrum.spines['top'].set_color(border)
    ax_spectrum.spines['left'].set_color(border)
    ax_spectrum.spines['right'].set_color(border)
    ax_spectrum.spines['bottom'].set_color(border)
    ax_tracks = fig.add_subplot(grid[3, 0])
    ax_tracks.patch.set_facecolor(figure_bg)
    spectrogram, colorbar, active_line, track_ID, refined_marker = plotting_spectrogram(time_range, ax_spectrogram, display_min, display_max, short_magnitude, short_frequency, short_mid_time, accepted_ID, active_time, active_freq, ID, grouped_refined_archive)
    spectrogram.set_animated(True)
    ax_spectrogram.xaxis.set_animated(True)
    ax_spectrogram.yaxis.set_animated(True)
    def spectrogram_update(spectrogram, colorbar, active_line, track_ID, refined_marker, time_range, ax, display_min, display_max, mag, freq, mid_time, accepted_ID, active_time, active_freq, ID, grouped_refined_archive):
        for lines in active_line:
            lines.remove()
        for texts in track_ID:
            texts.remove()
        for markers in refined_marker:
            markers.remove()
        spectrogram, colorbar, active_line, track_ID, refined_marker = plotting_spectrogram(time_range, ax, display_min, display_max, mag, freq, mid_time, accepted_ID, active_time, active_freq, ID, grouped_refined_archive, spectrogram, colorbar)
        ax_spectrogram.set_xlim(time_range[0], time_range[-1])
        return spectrogram, colorbar, active_line, track_ID, refined_marker
    spectrum_line, = ax_spectrum.plot(short_frequency, short_magnitude[-1], color = signal_cyan)
    spectrum_line.set_animated(True)
    ax_spectrum.xaxis.set_animated(True)
    ax_spectrum.set_title('CURRENT SPECTRUM', fontsize = 11, color = cyan)
    ax_spectrum.set_xlim(display_min, display_max)
    ax_spectrum.set_ylabel('Amplitude', color = text)
    ax_spectrum.set_xlabel('Frequency (Hz)', color = text)
    ax_spectrum.tick_params(color = text, labelcolor = text)
    def spectrum_update(short_frequency, short_magnitude):
        if len(short_magnitude) > 0 and len(short_frequency) > 0:
            spectrum_line.set_data(short_frequency, short_magnitude[-1])
    box = Rectangle((-0.02, 0.2), 0.56, 0.95, transform=ax_tracks.transAxes, fill = True, facecolor = panel_bg, edgecolor=text_border, linewidth=1, clip_on = False)
    ax_tracks.add_patch(box)
    ax_tracks.axis('off')
    track_scroll_index = [0]
    visible_track_count = 3
    tracks_text = []
    last_scroll = [0]
    ax_tracks.text(0, 1.03, 'TRACK REGISTRY', transform = ax_tracks.transAxes, color = '#B8FCFF', fontsize = 9, va = 'bottom', ha = 'left', clip_on = False)
    if len(accepted_ID) > 0:
        selected_ID = [accepted_ID[0]]
    else:
        selected_ID = [None]
    def selected_ID_update():
        if selected_ID[0] in accepted_ID:
            return
        else:
            if len(accepted_ID) > 0:
                selected_ID[0] = accepted_ID[0]
            else:
                selected_ID[0] = None
        return
    selected_ID_update()
    def draw_registry():
        for text_object in tracks_text:
            text_object.remove()
        tracks_text.clear()
        visible_slice = accepted_ID[track_scroll_index[0]:track_scroll_index[0] + visible_track_count]
        for j, i in enumerate(visible_slice):
            status = display_summary[i]['status']
            frequency = display_summary[i]['rough_frequency']
            frequency_display = '{:.2f}'.format(frequency)
            strength = display_summary[i]['strength']
            confidence = display_summary[i]['confidence_score']
            if i == selected_ID[0]:
                text_object = ax_tracks.text(0, 0.6 - j*0.2, 'TRACK {} | {} Hz | STRENGTH {:.2f} \nSTATUS {} | CONFIDENCE SCORE {:.2f} \n\n'.format(i, frequency_display, strength, status, confidence), fontsize = 8.5, color = active_online_individual)
            else:
                text_object = ax_tracks.text(0, 0.6 - j*0.2, 'TRACK {} | {} Hz | STRENGTH {:.2f} \nSTATUS {} | CONFIDENCE SCORE {:.2f} \n\n'.format(i, frequency_display, strength, status, confidence), fontsize = 8.5, color = text)
            tracks_text.append(text_object)
    draw_registry()
    def on_scroll(event):
        current_time = tm.time()
        if current_time - last_scroll[0] < 0.1:
            return
        last_scroll[0] = current_time
        if event.inaxes != ax_tracks:
            return
        max_scroll = max(0, len(accepted_ID) - visible_track_count)
        if event.step > 0:
            track_scroll_index[0] -= 1
        elif event.step < 0:
            track_scroll_index[0] += 1
        track_scroll_index[0] = max(0, min(track_scroll_index[0], max_scroll))
        draw_registry()
        ax_tracks.draw(fig.canvas.get_renderer())
        fig.canvas.blit(ax_tracks.bbox)
    waveform_line, = ax_waveform.plot(time_range, signal_range, color = signal_cyan)
    waveform_line.set_animated(True)
    ax_waveform.xaxis.set_animated(True)
    ax_waveform.set_ylabel('Amplitude', color = text)
    ax_waveform.set_xlabel('Time (s)', color = text)
    ax_waveform.set_title('WAVEFORM', fontsize = 11, color = cyan)
    ax_waveform.tick_params(color = text, labelcolor = text)
    def reduce_waveform_display(time_range, signal_range, max_points):
        # I'm preserving each bucket's minimum and maximum points so downsampling does not hide waveform peaks
        if len(signal_range) <= max_points:
            return time_range, signal_range
        bucket_count = max_points // 2
        bucket_size = int(np.ceil(len(signal_range) / bucket_count))
        display_time = []
        display_signal = []
        for start_index in range(0, len(signal_range), bucket_size):
            end_index = start_index + bucket_size
            if end_index > len(signal_range):
                end_index = len(signal_range)
            bucket_time = time_range[start_index:end_index]
            bucket_signal = signal_range[start_index:end_index]
            min_index = np.argmin(bucket_signal)
            max_index = np.argmax(bucket_signal)
            min_time = bucket_time[min_index]
            min_signal = bucket_signal[min_index]
            max_time = bucket_time[max_index]
            max_signal = bucket_signal[max_index]
            if min_index == max_index:
                display_time.append(min_time)
                display_signal.append(min_signal)
            elif min_index < max_index:
                display_time.append(min_time)
                display_signal.append(min_signal)
                display_time.append(max_time)
                display_signal.append(max_signal)
            else:
                display_time.append(max_time)
                display_signal.append(max_signal)
                display_time.append(min_time)
                display_signal.append(min_signal)
        display_time = np.array(display_time)
        display_signal = np.array(display_signal)
        return display_time, display_signal
    def waveform_update(axes, signal_range, time_range):
        if len(time_range) > 0 and len(signal_range) > 0:
            display_point_limit = int(axes.bbox.width * 2)
            if display_point_limit < 1000:
                display_point_limit = 1000
            display_time, display_signal = reduce_waveform_display(time_range, signal_range, display_point_limit)
            waveform_line.set_data(display_time, display_signal)
            axes.set_xlim(time_range[0], time_range[-1])
    grid_2 = grid[3, 1:3].subgridspec(2, 3, hspace = 1.2, wspace = 0.55)
    ax_telemetry = fig.add_subplot(grid_2[0:2, 0])
    ax_telemetry.patch.set_facecolor(figure_bg)
    ax_freq_history = fig.add_subplot(grid_2[0, 1])
    ax_freq_history.patch.set_facecolor(panel_bg)
    ax_freq_history.spines['top'].set_color(border)
    ax_freq_history.spines['left'].set_color(border)
    ax_freq_history.spines['right'].set_color(border)
    ax_freq_history.spines['bottom'].set_color(border)
    ax_strength_history = fig.add_subplot(grid_2[0, 2])
    ax_strength_history.patch.set_facecolor(panel_bg)
    ax_strength_history.spines['top'].set_color(border)
    ax_strength_history.spines['left'].set_color(border)
    ax_strength_history.spines['right'].set_color(border)
    ax_strength_history.spines['bottom'].set_color(border)
    ax_snr_history = fig.add_subplot(grid_2[1, 1])
    ax_snr_history.patch.set_facecolor(panel_bg)
    ax_snr_history.spines['top'].set_color(border)
    ax_snr_history.spines['left'].set_color(border)
    ax_snr_history.spines['right'].set_color(border)
    ax_snr_history.spines['bottom'].set_color(border)
    ax_bandwidth_history = fig.add_subplot(grid_2[1, 2])
    ax_bandwidth_history.patch.set_facecolor(panel_bg)
    ax_bandwidth_history.spines['top'].set_color(border)
    ax_bandwidth_history.spines['left'].set_color(border)
    ax_bandwidth_history.spines['right'].set_color(border)
    ax_bandwidth_history.spines['bottom'].set_color(border)
    ax_strength_history.set_xlabel('Time (s)', fontsize = 7, color = text)
    ax_strength_history.set_title('STRENGTH - TIME', fontsize = 8, color = cyan)
    ax_strength_history.tick_params(labelsize = 6, color = text, labelcolor = text)
    ax_freq_history.set_xlabel('Time (s)', fontsize = 7, color = text)
    ax_freq_history.set_title('FREQUENCY (Hz) - TIME', fontsize = 8, color = cyan)
    ax_freq_history.tick_params(labelsize = 6, color = text, labelcolor = text)
    ax_snr_history.set_xlabel('Time (s)', fontsize = 7, color = text)
    ax_snr_history.set_title('SNR - TIME', fontsize = 8, color = cyan)
    ax_snr_history.tick_params(labelsize = 6, color = text, labelcolor = text)
    ax_bandwidth_history.set_xlabel('Time (s)', fontsize = 7, color = text)
    ax_bandwidth_history.set_title('BANDWIDTH (Hz) - TIME', fontsize = 8, color = cyan)
    ax_bandwidth_history.tick_params(labelsize = 6, color = text, labelcolor = text)
    compact_tick_formatter = FuncFormatter(compact_tick)
    ax_spectrogram.xaxis.set_major_formatter(compact_tick_formatter)
    ax_spectrogram.yaxis.set_major_formatter(compact_tick_formatter)
    ax_waveform.xaxis.set_major_formatter(compact_tick_formatter)
    ax_waveform.yaxis.set_major_formatter(compact_tick_formatter)
    ax_spectrum.xaxis.set_major_formatter(compact_tick_formatter)
    ax_spectrum.yaxis.set_major_formatter(compact_tick_formatter)
    ax_freq_history.xaxis.set_major_formatter(compact_tick_formatter)
    ax_freq_history.yaxis.set_major_formatter(compact_tick_formatter)
    ax_strength_history.xaxis.set_major_formatter(compact_tick_formatter)
    ax_strength_history.yaxis.set_major_formatter(compact_tick_formatter)
    ax_snr_history.xaxis.set_major_formatter(compact_tick_formatter)
    ax_snr_history.yaxis.set_major_formatter(compact_tick_formatter)
    ax_bandwidth_history.xaxis.set_major_formatter(compact_tick_formatter)
    ax_bandwidth_history.yaxis.set_major_formatter(compact_tick_formatter)
    ax_telemetry.axis('off')
    y_val = [0.8299105339105337, 0.6056103896103895, 0.40374025974025973]
    telemetry_text = []
    row_offset = {'track': 0, 'status': -11, 'spectral': -22, 'rough': -44, 'refined': -55, 'strength': -66, 'snr': -88, 'bandwidth': -99, 'drift': -121, 'trend': -132, 'freq_std': -154, 'strength_std': -165, 'confidence': -176}
    labels = {'track': 'TRACK', 'status': 'STATUS', 'spectral': 'SPECTRAL STATE', 'rough': 'ROUGH FREQUENCY (Hz)', 'refined': 'REFINED FREQUENCY (Hz)', 'strength': 'STRENGTH', 'snr': 'SNR', 'bandwidth': 'BANDWIDTH (Hz)', 'drift': 'FREQUENCY DRIFT (Hz/s)', 'trend': 'STRENGTH TREND (/s)', 'freq_std': 'FREQUENCY STD (Hz)', 'strength_std': 'STRENGTH STD', 'confidence': 'CONFIDENCE'}
    for row in labels:
        ax_telemetry.annotate(labels[row], xy = (-1.2, 1.05), xycoords = 'axes fraction', xytext = (0, row_offset[row]), textcoords = 'offset points', ha = 'left', va = 'center', fontsize = 9, color = text, clip_on = False)
    def draw_telemetry():
        for telemetry_object in telemetry_text:
            telemetry_object.remove()
        telemetry_text.clear()
        if selected_ID[0] is not None:
            selected_track = display_summary[selected_ID[0]]
            if len(selected_track['confirmed']) > 0:
                refined_frequency = selected_track['confirmed']
                spectral_state = 'INDIVIDUAL'
            elif len(selected_track['blended']) > 0:
                refined_frequency = selected_track['blended']
                spectral_state = 'BLENDED'
            elif len(selected_track['uncertain']) > 0:
                refined_frequency = selected_track['uncertain']
                spectral_state = 'UNCERTAIN'
            else:
                refined_frequency = None
                spectral_state = 'N/A'
            if refined_frequency is not None:
                refined_string = []
                for z in refined_frequency[:3]:
                    refined_string.append(compact_number(z))
            
                if len(refined_frequency) > 3:
                    refined_freq = ','.join(refined_string) + ' +' + str(len(refined_frequency) - 3)
                else:
                    refined_freq = ', '.join(refined_string)
            
                if len(refined_freq) > 26:
                    refined_string = []
                    for z in refined_frequency[:2]:
                        refined_string.append(compact_number(z))
            
                    if len(refined_frequency) > 2:
                        refined_freq = ','.join(refined_string) + ' +' + str(len(refined_frequency) - 2)
                    else:
                        refined_freq = ', '.join(refined_string)
            else:
                refined_freq = 'N/A'
            if selected_track['latest_snr'] is None:
                latest_snr = 'N/A'
            else:
                latest_snr = '{:.2f}'.format(selected_track['latest_snr'])
            if selected_track['latest_bandwidth'] is None:
                latest_bandwidth = 'N/A'
            else:
                latest_bandwidth = compact_number(selected_track['latest_bandwidth'])
            if selected_track['net_freq_drift_rate'] is None:
                net_freq_drift_rate = 'N/A'
            else:
                net_freq_drift_rate = compact_number(selected_track['net_freq_drift_rate'])
            if selected_track['net_strength_change_rate'] is None:
                net_strength_change_rate = 'N/A'
            else:
                net_strength_change_rate = '{:.4g}'.format(selected_track['net_strength_change_rate'])            
            if selected_track['frequency_std'] is None:
                frequency_std = 'N/A'
            else:
                frequency_std = compact_number(selected_track['frequency_std'])
            if selected_track['strength_std'] is None:
                strength_std = 'N/A'
            else:
                strength_std = '{:.4g}'.format(selected_track['strength_std'])
            if selected_track['confidence_score'] is None:
                confidence_score = 'N/A'
            else:
                confidence_score = '{:.2f}'.format(selected_track['confidence_score'])
            rough_frequency = compact_number(selected_track['rough_frequency'])
            values = {'track': selected_ID[0], 'rough': '{}'.format(rough_frequency), 'refined': '{}'.format(refined_freq), 'strength': '{:.4g}'.format(selected_track['strength']), 'snr': latest_snr, 'bandwidth': '{}'.format(latest_bandwidth), 'drift': '{}'.format(net_freq_drift_rate), 'trend': '{}'.format(net_strength_change_rate), 'freq_std': '{}'.format(frequency_std), 'strength_std': strength_std, 'confidence': confidence_score}
            for row in values:
                telemetry_object = ax_telemetry.annotate(values[row], xy = (0, 1.05), xycoords = 'axes fraction', xytext = (0, row_offset[row]), textcoords = 'offset points', ha = 'left', va = 'center', fontsize = 9, color = text)
                telemetry_text.append(telemetry_object)
            if selected_track['status'] == 'ACTIVE':
                telemetry_object = ax_telemetry.annotate('{}'.format(selected_track['status']), xy = (0, 1.05), xycoords = 'axes fraction', xytext = (0, row_offset['status']), textcoords = 'offset points', color = active_online_individual, ha = 'left', va = 'center', fontsize = 9)
                telemetry_text.append(telemetry_object)
            elif selected_track['status'] == 'COASTING' or selected_track['status'] == 'CANDIDATE':
                telemetry_object = ax_telemetry.annotate('{}'.format(selected_track['status']), xy = (0, 1.05), xycoords = 'axes fraction', xytext = (0, row_offset['status']), textcoords = 'offset points', color = candidate_coasting_uncertain, ha = 'left', va = 'center', fontsize = 9)
                telemetry_text.append(telemetry_object)
            elif selected_track['status'] == 'TERMINATED' or selected_track['status'] == 'LOST':
                telemetry_object = ax_telemetry.annotate('{}'.format(selected_track['status']), xy = (0, 1.05), xycoords = 'axes fraction', xytext = (0, row_offset['status']), textcoords = 'offset points', color = lost_terminated_warnings, ha = 'left', va = 'center', fontsize = 9)
                telemetry_text.append(telemetry_object)
            else:
                telemetry_object = ax_telemetry.annotate('NO STATUS FOUND', xy = (0, 1.05), xycoords = 'axes fraction', xytext = (0, row_offset['status']), textcoords = 'offset points', color = lost_terminated_warnings, ha = 'left', va = 'center', fontsize = 9)
                telemetry_text.append(telemetry_object)
            if spectral_state == 'INDIVIDUAL':
                telemetry_object = ax_telemetry.annotate('{}'.format(spectral_state), xy = (0, 1.05), xycoords = 'axes fraction', xytext = (0, row_offset['spectral']), textcoords = 'offset points', color = active_online_individual, ha = 'left', va = 'center', fontsize = 9)
                telemetry_text.append(telemetry_object)
            elif spectral_state == 'BLENDED' or spectral_state == 'UNCERTAIN':
                telemetry_object = ax_telemetry.annotate('{}'.format(spectral_state), xy = (0, 1.05), xycoords = 'axes fraction', xytext = (0, row_offset['spectral']), textcoords = 'offset points', color = candidate_coasting_uncertain, ha = 'left', va = 'center', fontsize = 9)
                telemetry_text.append(telemetry_object)
            else:
                telemetry_object = ax_telemetry.annotate('NO SPECTRAL STATE FOUND', xy = (0, 1.05), xycoords = 'axes fraction', xytext = (0, row_offset['spectral']), textcoords = 'offset points', color = lost_terminated_warnings, ha = 'left', va = 'center', fontsize = 9)
                telemetry_text.append(telemetry_object)
            for t in telemetry_text:
                t.set_animated(True)
        else:
            return
    draw_telemetry()
    strength_line, = ax_strength_history.plot([], [], color = signal_cyan)
    strength_line.set_animated(True)
    ax_strength_history.xaxis.set_animated(True)
    ax_strength_history.yaxis.set_animated(True)
    freq_line, = ax_freq_history.plot([], [], color = signal_cyan)
    freq_line.set_animated(True)
    ax_freq_history.xaxis.set_animated(True)
    ax_freq_history.yaxis.set_animated(True)
    snr_line, = ax_snr_history.plot([], [], color = signal_cyan)
    snr_line.set_animated(True)
    ax_snr_history.xaxis.set_animated(True)
    ax_snr_history.yaxis.set_animated(True)
    bw_line, = ax_bandwidth_history.plot([], [], color = signal_cyan)
    bw_line.set_animated(True)
    ax_bandwidth_history.xaxis.set_animated(True)
    ax_bandwidth_history.yaxis.set_animated(True)
    def draw_graphs():
        ax_strength_history.set_xlim(time_range[0], time_range[-1])
        ax_freq_history.set_xlim(time_range[0], time_range[-1])
        ax_snr_history.set_xlim(time_range[0], time_range[-1])
        ax_bandwidth_history.set_xlim(time_range[0], time_range[-1])
        if selected_ID[0] is not None:
            selected_track = display_summary[selected_ID[0]]
            start_index = bisect_left(selected_track['time_history'], time_range[0])
            end_index = bisect_right(selected_track['time_history'], time_range[-1])
            time_history = selected_track['time_history'][start_index:end_index]
            strength_history = selected_track['strength_history'][start_index:end_index]
            frequency_history = selected_track['frequency_history'][start_index:end_index]
            snr_history = selected_track['snr_history'][start_index:end_index]
            bandwidth_history = selected_track['bandwidth_history'][start_index:end_index]
            snr_plot = []
            time_plot_snr = []
            for snr in range(len(snr_history)):
                if snr_history[snr] is not None:
                    snr_plot.append(snr_history[snr])
                    time_plot_snr.append(time_history[snr])
            bw_plot = []
            time_plot_bw = []
            for bw in range(len(bandwidth_history)):
                if bandwidth_history[bw] is not None:
                    bw_plot.append(bandwidth_history[bw])
                    time_plot_bw.append(time_history[bw])
            if len(strength_history) > 1:
                strength_line.set_data(time_history, strength_history)
                strength_average = np.average(strength_history)
                str_above = strength_average * 1.1
                str_below = strength_average * 0.9
                ax_strength_history.set_ylim(str_below, str_above)
            else:
                strength_line.set_data([], [])
            if len(frequency_history) > 1:
                freq_line.set_data(time_history, frequency_history)
                frequency_center = selected_track['rough_frequency']
                freq_below = frequency_center - 1
                freq_above = frequency_center + 1
                ax_freq_history.set_ylim(freq_below, freq_above)
            else:
                freq_line.set_data([], [])
            snr_line.set_data(time_plot_snr, snr_plot)
            if len(snr_plot) > 0:
                snr_average = np.average(snr_plot)
                snr_below = snr_average * 0.8
                snr_above = snr_average * 1.2
                ax_snr_history.set_ylim(snr_below, snr_above)
            bw_line.set_data(time_plot_bw, bw_plot)
            ax_bandwidth_history.set_ylim(0, 5)
        else:
            strength_line.set_data([], [])
            freq_line.set_data([], [])
            snr_line.set_data([], [])
            bw_line.set_data([], [])
    draw_graphs()
    box_2 = Rectangle((-1.3, -0.4), 2.55, 1.55, transform = ax_telemetry.transAxes, fill = True, facecolor = panel_bg, edgecolor=text_border, linewidth=1, clip_on = False)
    ax_telemetry.add_patch(box_2)
    def on_click(event):
        if len(accepted_ID) == 0:
            return
        distance = []
        if event.inaxes != ax_tracks:
            return
        distance.append(np.abs(event.ydata - y_val[0]))
        distance.append(np.abs(event.ydata - y_val[1]))
        distance.append(np.abs(event.ydata - y_val[2]))
        index_click = np.argmin(distance)
        visible_slice = accepted_ID[track_scroll_index[0]:track_scroll_index[0] + visible_track_count]
        if index_click < len(visible_slice):
            selected_ID[0] = visible_slice[index_click]
        draw_registry()
        ax_tracks.draw(fig.canvas.get_renderer())
        fig.canvas.blit(ax_tracks.bbox)
        draw_telemetry()
        fig.canvas.restore_region(telemetry_background)
        for t in telemetry_text:
            ax_telemetry.draw_artist(t)
        fig.canvas.blit(telemetry_bbox)
        draw_graphs()                
        fig.canvas.restore_region(strength_history_click_background)
        ax_strength_history.draw_artist(ax_strength_history.yaxis)
        ax_strength_history.draw_artist(strength_line)
        fig.canvas.blit(strength_history_bbox)
        fig.canvas.restore_region(freq_history_click_background)
        ax_freq_history.draw_artist(ax_freq_history.yaxis)
        ax_freq_history.draw_artist(freq_line)
        fig.canvas.blit(freq_history_bbox)
        fig.canvas.restore_region(snr_history_click_background)
        ax_snr_history.draw_artist(ax_snr_history.yaxis)
        ax_snr_history.draw_artist(snr_line)
        fig.canvas.blit(snr_history_bbox)
        fig.canvas.restore_region(bandwidth_history_click_background)
        ax_bandwidth_history.draw_artist(ax_bandwidth_history.yaxis)
        ax_bandwidth_history.draw_artist(bw_line)
        fig.canvas.blit(bandwidth_history_bbox)
        draw_header()
        fig.canvas.restore_region(header_background)
        for header_object in header_text:
            ax_header.draw_artist(header_object)
        fig.canvas.blit(header_bbox)
    ax_header.axis('off')
    blacksite_header_text = ax_header.text(0.05, -0.8, 'BLACKSITE // ', fontsize = 12, color = cyan)
    platform_status_text = ax_header.text(0, -0.8, '{}'.format(platform_status), fontsize = 12, color = active_online_individual)
    active_header_text = ax_header.text(0, -0.8, ' | ACTIVE TRACKS ', fontsize = 12, color = cyan)
    active_counter_text = ax_header.text(0, -0.8, '{}'.format(0), fontsize = 12, color = active_online_individual)
    selected_header_text = ax_header.text(0, -0.8, ' | SELECTED ', fontsize = 12, color = cyan)
    selected_ID_text = ax_header.text(0, -0.8, '{}'.format(selected_ID[0]), fontsize = 12, color = active_online_individual)
    display_header_text = ax_header.text(0, -0.8, ' | DISPLAY ', fontsize = 12, color = cyan)
    freq_display_text = ax_header.text(0, -0.8, '{}-{}Hz'.format(compact_number(display_min), compact_number(display_max)), fontsize = 12, color = active_online_individual)
    fft_header_text = ax_header.text(0, -0.8, ' | FFT ', fontsize = 12, color = cyan)
    short_fft_text = ax_header.text(0, -0.8, '{}'.format(compact_number(short_analysis_sample)), fontsize = 12, color = active_online_individual)
    hop_header_text = ax_header.text(0, -0.8, ' | HOP ', fontsize = 12, color = cyan)
    short_hop_text = ax_header.text(0, -0.8, '{}'.format(compact_number(hop_size)), fontsize = 12, color = active_online_individual)
    mode_header_text = ax_header.text(0, -0.8, ' | MODE: ', fontsize = 12, color = cyan)
    platform_mode_text = ax_header.text(0, -0.8, '{}'.format(platform_mode), fontsize = 12, color = active_online_individual)
    def position_header_text(previous_text, current_text):
        renderer = fig.canvas.get_renderer()
        previous_box = previous_text.get_window_extent(renderer = renderer)
        next_position = ax_header.transData.inverted().transform((previous_box.x1, previous_box.y1))
        current_text.set_x(next_position[0])
    def position_header():
        position_header_text(blacksite_header_text, platform_status_text)
        position_header_text(platform_status_text, active_header_text)
        position_header_text(active_header_text, active_counter_text)
        position_header_text(active_counter_text, selected_header_text)
        position_header_text(selected_header_text, selected_ID_text)
        position_header_text(selected_ID_text, display_header_text)
        position_header_text(display_header_text, freq_display_text)
        position_header_text(freq_display_text, fft_header_text)
        position_header_text(fft_header_text, short_fft_text)
        position_header_text(short_fft_text, hop_header_text)
        position_header_text(hop_header_text, short_hop_text)
        position_header_text(short_hop_text, mode_header_text)
        position_header_text(mode_header_text, platform_mode_text)
    position_header()
    blacksite_header_text.set_animated(True)
    platform_status_text.set_animated(True)
    active_header_text.set_animated(True)
    active_counter_text.set_animated(True)
    selected_header_text.set_animated(True)
    selected_ID_text.set_animated(True)
    display_header_text.set_animated(True)
    freq_display_text.set_animated(True)
    fft_header_text.set_animated(True)
    short_fft_text.set_animated(True)
    hop_header_text.set_animated(True)
    short_hop_text.set_animated(True)
    mode_header_text.set_animated(True)
    platform_mode_text.set_animated(True)
    header_text = [blacksite_header_text, platform_status_text, active_header_text, active_counter_text, selected_header_text, selected_ID_text, display_header_text, freq_display_text, fft_header_text, short_fft_text, hop_header_text, short_hop_text, mode_header_text, platform_mode_text]
    def draw_header():
        active_counter = 0
        for i in display_summary.keys():
            if display_summary[i]['status'] == 'ACTIVE':
                active_counter+=1
        platform_status_text.set_text(platform_status)
        active_counter_text.set_text(active_counter)
        if selected_ID[0] is not None:
            selected_ID_text.set_text(selected_ID[0])
        else:
            selected_ID_text.set_text('--')
        freq_display_text.set_text('{}-{}Hz'.format(compact_number(display_min), compact_number(display_max)))
        short_fft_text.set_text(compact_number(short_analysis_sample))
        short_hop_text.set_text(compact_number(hop_size))
        platform_mode_text.set_text(platform_mode)
        position_header()
    def pause_callback(event):
        nonlocal platform_mode
        if finished[0] == True:
            return
        if paused[0] == False:
            paused[0] = True
            platform_mode = 'PAUSED'
            timer.stop()
            draw_header()
            fig.canvas.restore_region(header_background)
            for header_object in header_text:
                ax_header.draw_artist(header_object)
            fig.canvas.blit(header_bbox)
        else:
            paused[0] = False
            platform_mode = 'LIVE'
            timer.start()
            draw_header()
            fig.canvas.restore_region(header_background)
            for header_object in header_text:
                ax_header.draw_artist(header_object)
            fig.canvas.blit(header_bbox)
            refresh_freq_slider()
    pause_ax = fig.add_axes([0.88, 0.94, 0.08, 0.04])
    pause_ax.patch.set_facecolor(figure_bg)
    pause_button = Button(pause_ax, 'PAUSE / RESUME', color = panel_bg, hovercolor = active_online_individual)
    pause_button.label.set_color(text)
    pause_ax.spines['top'].set_color(border)
    pause_ax.spines['left'].set_color(border)
    pause_ax.spines['right'].set_color(border)
    pause_ax.spines['bottom'].set_color(border)
    fig.pause_button = pause_button
    pause_button.on_clicked(pause_callback)
    def restart_callback(event):
        nonlocal platform_mode, existing_completed_track_history, existing_id_counter, signal_range, time_range, short_magnitude, short_frequency, short_mid_time, long_magnitude, long_frequency, long_mid_time, display_summary, accepted_ID, active_time, active_freq, ID
        timer.stop()
        live_index[0] = short_analysis_sample
        timer_counter[0] = 0
        latest_processed_index[0] = None
        paused[0] = False
        finished[0] = False
        platform_mode = 'LIVE'
        existing_completed_track_history.clear()
        existing_lost.clear()
        existing_terminated.clear()
        existing_id_counter = 0
        track_history_archive.clear()
        refined_history_archive.clear()
        grouped_refined_archive.clear()
        same_window_archive.clear()
        selected_ID[0] = None
        track_scroll_index[0] = 0
        signal_range, time_range, short_magnitude, short_frequency, short_mid_time, long_magnitude, long_frequency, long_mid_time, existing_completed_track_history, display_summary, accepted_ID, active_time, active_freq, ID = buffer_processing()
        fast_refresh_display()
        dense_refresh_display()
        timer.start()
    restart_ax = fig.add_axes([0.78, 0.94, 0.08, 0.04])
    restart_ax.patch.set_facecolor(figure_bg)
    restart_button = Button(restart_ax, 'RESTART', color = panel_bg, hovercolor = active_online_individual)
    restart_button.label.set_color(text)
    restart_ax.spines['top'].set_color(border)
    restart_ax.spines['left'].set_color(border)
    restart_ax.spines['right'].set_color(border)
    restart_ax.spines['bottom'].set_color(border)
    fig.restart_button = restart_button
    restart_button.on_clicked(restart_callback)
    freq_slider_ax = fig.add_axes([0.12, 0.95, 0.20, 0.025])
    freq_slider_ax.set_facecolor(panel_bg)
    freq_slider = RangeSlider(freq_slider_ax, 'DISPLAY Hz', 0, nyquist, valinit = (display_min, display_max), valstep = 1)
    freq_slider.label.set_color(text)
    freq_slider.valtext.set_color(text)
    freq_slider.track.set_facecolor(panel_bg)
    freq_slider.track.set_edgecolor(border)
    freq_slider.poly.set_facecolor(cyan)
    freq_slider.valtext.set_visible(False)
    freq_slider.poly.set_animated(True)
    for handle in freq_slider._handles:
        handle.set_markerfacecolor(panel_bg)
        handle.set_markeredgecolor(cyan)
    for handle in freq_slider._handles:
        handle.set_animated(True)
    fig.freq_slider = freq_slider
    freq_slider.drawon = False
    freq_slider_changed = [False]
    def freq_slider_move(value):
        freq_slider_changed[0] = True
        fig.canvas.restore_region(freq_slider_background)
        freq_slider_ax.draw_artist(freq_slider.poly)
        for handle in freq_slider._handles:
            freq_slider_ax.draw_artist(handle)
        fig.canvas.blit(freq_slider_bbox)
    def freq_slider_release(value):
        nonlocal display_min, display_max
        if freq_slider_changed[0] == False:
            return
        else:
            display_min, display_max = freq_slider.val
            freq_slider_changed[0] = False
            ax_spectrum.set_xlim(display_min, display_max)
            ax_spectrogram.set_ylim(display_min, display_max)
            fast_refresh_display()
            draw_header()
            fig.canvas.restore_region(header_background)
            for header_object in header_text:
                ax_header.draw_artist(header_object)
            fig.canvas.blit(header_bbox)
    def refresh_freq_slider():
        fig.canvas.restore_region(freq_slider_background)
        freq_slider_ax.draw_artist(freq_slider.poly)
        for handle in freq_slider._handles:
            freq_slider_ax.draw_artist(handle)
        fig.canvas.blit(freq_slider_bbox)
    freq_slider.on_changed(freq_slider_move)
    export_ax = fig.add_axes([0.68, 0.94, 0.08, 0.04])
    export_ax.patch.set_facecolor(figure_bg)
    export_button = Button(export_ax, 'EXPORT', color = panel_bg, hovercolor = active_online_individual)
    export_button.label.set_color(text)
    export_ax.spines['top'].set_color(border)
    export_ax.spines['left'].set_color(border)
    export_ax.spines['right'].set_color(border)
    export_ax.spines['bottom'].set_color(border)
    def export_helper():
        export_button.label.set_text('EXPORT')
        export_ax.draw(fig.canvas.get_renderer())
        fig.canvas.blit(export_ax.bbox)
    export_timer = fig.canvas.new_timer(2000)
    fig.export_timer = export_timer
    export_timer.single_shot = True
    export_timer.add_callback(export_helper)
    def export_callback(event):
        counter = 1
        if len(display_summary) == 0:
            export_button.label.set_text('NO DATA!')
            export_ax.draw(fig.canvas.get_renderer())
            fig.canvas.blit(export_ax.bbox)
            export_timer.start()
            return
        folder_path = QtWidgets.QFileDialog.getExistingDirectory(manager.window, 'EXPORT CURRENT BLACKSITE ANALYSIS')
        if folder_path:
            latest_export = np.round(time_range[-1], 2)
            history_path = os.path.join(folder_path, '{}_BLACKSITE_track_history_{}s.csv'.format(source_name, latest_export))
            summary_path = os.path.join(folder_path, '{}_BLACKSITE_summary_{}s.csv'.format(source_name, latest_export))
            while os.path.exists(history_path) or os.path.exists(summary_path):
                history_path = os.path.join(folder_path, '{}_BLACKSITE_track_history_{}s({}).csv'.format(source_name, latest_export, counter))
                summary_path = os.path.join(folder_path, '{}_BLACKSITE_summary_{}s({}).csv'.format(source_name, latest_export, counter))
                counter += 1
            try:
                export_track(display_summary, history_path)
                export_summary(display_summary, summary_path)
                export_button.label.set_text('EXPORTED!')
                export_timer.start()
            except OSError:
                if os.path.exists(history_path):
                    os.remove(history_path)
                if os.path.exists(summary_path):
                    os.remove(summary_path)
                export_button.label.set_text('FAILED!')
                export_timer.start()
            export_ax.draw(fig.canvas.get_renderer())
            fig.canvas.blit(export_ax.bbox)
    export_button.on_clicked(export_callback)
    fig.canvas.mpl_connect('scroll_event', on_scroll)
    fig.canvas.mpl_connect('button_press_event', on_click)
    fig.canvas.mpl_connect('button_release_event', freq_slider_release)
    fig.canvas.draw()
    def recapture_background():
        nonlocal telemetry_background, freq_slider_bbox, freq_slider_background, spectrum_bbox, bandwidth_history_background, snr_history_background, freq_history_background, strength_history_background, spectrum_background, waveform_background, spectrogram_background, header_background, telemetry_bbox, header_bbox, spectrogram_bbox, waveform_bbox, strength_history_bbox, freq_history_bbox, snr_history_bbox, bandwidth_history_bbox
        telemetry_bbox = box_2.get_window_extent(fig.canvas.get_renderer()).padded(10)
        telemetry_background = fig.canvas.copy_from_bbox(telemetry_bbox)
        header_bbox = ax_header.get_tightbbox(fig.canvas.get_renderer()).padded(20)
        header_background = fig.canvas.copy_from_bbox(header_bbox)
        spectrogram_bbox = ax_spectrogram.get_tightbbox(fig.canvas.get_renderer()).padded(25)
        spectrogram_background = fig.canvas.copy_from_bbox(spectrogram_bbox)
        waveform_bbox = ax_waveform.get_tightbbox(fig.canvas.get_renderer()).padded(40)
        waveform_background = fig.canvas.copy_from_bbox(waveform_bbox)
        spectrum_bbox = ax_spectrum.get_tightbbox(fig.canvas.get_renderer()).padded(10)
        spectrum_background = fig.canvas.copy_from_bbox(spectrum_bbox)
        strength_history_bbox = ax_strength_history.get_tightbbox(fig.canvas.get_renderer()).padded(10)
        strength_history_background = fig.canvas.copy_from_bbox(strength_history_bbox)
        freq_history_bbox = ax_freq_history.get_tightbbox(fig.canvas.get_renderer()).padded(10)
        freq_history_background = fig.canvas.copy_from_bbox(freq_history_bbox)
        snr_history_bbox = ax_snr_history.get_tightbbox(fig.canvas.get_renderer()).padded(10)
        snr_history_background = fig.canvas.copy_from_bbox(snr_history_bbox)
        bandwidth_history_bbox = ax_bandwidth_history.get_tightbbox(fig.canvas.get_renderer()).padded(10)
        bandwidth_history_background = fig.canvas.copy_from_bbox(bandwidth_history_bbox)       
        freq_slider_bbox = freq_slider_ax.bbox.padded(20)
        freq_slider_background = fig.canvas.copy_from_bbox(freq_slider_bbox)
    recapture_background()
    refresh_freq_slider()
    fast_refresh_display()
    dense_refresh_display()
    def on_resize(event):
        resize_pending[0] = True
        timer_resize.stop()
        timer_resize.start()
    def resize_finish():
        if resize_pending[0] == False:
            return
        else:
            resize_pending[0] = False
            fig.canvas.draw()
            recapture_background()
            fast_refresh_display()
            dense_refresh_display()
    fig.canvas.mpl_connect('resize_event', on_resize)
    def timer_update():
        if resize_pending[0] == True:
            return
        timer_counter[0] += 1
        nonlocal platform_mode, signal_range, time_range, short_magnitude, short_frequency, short_mid_time, long_magnitude, long_frequency, long_mid_time, display_summary, accepted_ID, active_time, active_freq, ID
        if live_index[0] >= len(signal):
            # Here I'm refreshing the spectrogram on the final frame so the last
            # tracks and IDs are drawn before playback stops
            fast_refresh_display(True)
            timer.stop()
            finished[0] = True
            platform_mode = 'FINISHED'
            draw_header()
            fig.canvas.restore_region(header_background)
            for header_object in header_text:
                ax_header.draw_artist(header_object)
            fig.canvas.blit(header_bbox)
            refresh_freq_slider()
            return
        else:
            signal_range, time_range, short_magnitude, short_frequency, short_mid_time, long_magnitude, long_frequency, long_mid_time, _, display_summary, accepted_ID, active_time, active_freq, ID = live_update(live_index, live_step)            
        if timer_counter[0] % 2 == 0:
            fast_refresh_display(False)
            dense_timer.stop()
            dense_timer.start()
        else:
            fast_refresh_display(False)
            spectrogram_timer.stop()
            spectrogram_timer.start()
    # Below I'm running the heavier spectrogram and dense panel redraws on separate one shot
    # timers so the main timer can return control to Qt and keep the UI responsive
    spectrogram_timer = fig.canvas.new_timer(1)
    fig.spectrogram_timer = spectrogram_timer
    spectrogram_timer.single_shot = True
    spectrogram_timer.add_callback(spectrogram_refresh_display)
    dense_timer = fig.canvas.new_timer(1)
    fig.dense_timer = dense_timer
    dense_timer.single_shot = True
    dense_timer.add_callback(dense_refresh_display)
    timer = fig.canvas.new_timer(500)
    fig.timer = timer
    timer.add_callback(timer_update)
    timer.start()
    timer_resize = fig.canvas.new_timer(150)
    fig.timer_resize = timer_resize
    timer_resize.add_callback(resize_finish)
    timer_resize.single_shot = True
    plt.show()
    return

def launcher():
    window = QtWidgets.QWidget()
    window.setStyleSheet('QWidget {background-color: #07111a; color: #00e5ff;} QLabel {color: #B8FCFF;background-color: transparent;} QLineEdit {background-color: #0b1a26; color: #00e5ff; border: 1px solid #167f8f; padding: 7px;} QPushButton {background-color: #0b1a26; color: #39f6ff; border: 1px solid #167f8f; padding: 8px;} QPushButton:hover {background-color: #07111a; border: 1px solid #39f6ff;} QPushButton:pressed {background-color: #0b1a26; border: 1px solid #00e5ff;}')
    window.setWindowTitle('BLACKSITE LAUNCHER')
    window.resize(550, 450)
    layout = QtWidgets.QGridLayout(window)
    title_label = QtWidgets.QLabel('BLACKSITE v1.0')
    title_label.setStyleSheet('font-size: 36px; font-weight: bold; color: #39f6ff;')
    info_label = QtWidgets.QLabel('BLACKSITE currently accepts only CSV and WAV files :(\n\nPlease make sure your CSV file:\n• Contains a header row with exactly one time column and one signal column\n• Uses a comma, semicolon, or tab delimiter\n• Contains only finite numeric time and signal values\n• Has approximately uniform sample spacing\n• Uses a supported time unit (seconds by default)\n\nAnd please make sure your WAV file:\n• Uses uncompressed PCM\n• Is in mono or multichannel \n• Uses 8-bit, 16-bit, 24-bit, or 32-bit PCM\n\nPlease also make sure your input is at least 1 second long\nFor the complete list of requirements, please visit my GitHub page\n\nTHANK YOU FOR USING BLACKSITE!! :))))')
    info_label.setWordWrap(True)
    info_label.setStyleSheet('font-size: 13px;')
    warning_label = QtWidgets.QLabel('PERFORMANCE NOTE: Dense audio or signals with many simultaneous frequencies at\n192 kHz or higher may significantly increase CPU usage and UI lag')
    warning_label.setWordWrap(True)
    warning_label.setStyleSheet('font-size: 11px; color: #FFB547;')
    file_label = QtWidgets.QLabel('CSV/WAV FILE')
    path_entry = QtWidgets.QLineEdit()
    browse_button = QtWidgets.QPushButton('BROWSE')
    launch_button = QtWidgets.QPushButton('LAUNCH')
    status_label = QtWidgets.QLabel("")
    layout.addWidget(title_label, 0, 0, 1, 2)
    layout.addWidget(info_label, 1, 0, 1, 2)
    layout.addWidget(warning_label, 2, 0, 1, 2)
    layout.addWidget(file_label, 3, 0)
    layout.addWidget(path_entry, 3, 1)
    layout.addWidget(browse_button, 4, 0)
    layout.addWidget(launch_button, 4, 1)
    layout.addWidget(status_label, 5, 0, 1, 2)
    layout.setContentsMargins(30, 30, 30, 30)
    layout.setVerticalSpacing(20)
    layout.setHorizontalSpacing(15)
    status_label.setStyleSheet('color: #FF5A4F; font-weight: bold;')
    def browse_file():
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(window, 'Select BLACKSITE input', '', 'Supported files (*.csv *.wav);;CSV files (*.csv);;WAV files (*.wav)')
        if file_path:
            path_entry.setText(file_path)
    def file_launch():
        file_path = path_entry.text()
        extension = os.path.splitext(file_path)[1].lower()
        if extension == '.csv':
            results = system_input(file_path)
        elif extension == '.wav':
            results = wav_input(file_path)
        else:
            results = None
        if results is None:
            status_label.setText('ERROR: INVALID OR UNSUPPORTED FILE')
        else:
            signal, time = results
            status_label.setText('')
            launch_button.setEnabled(False)
            dashboard(signal, time, file_path, dashboard_close)
    def dashboard_close():
        launch_button.setEnabled(True)
    browse_button.clicked.connect(browse_file)
    launch_button.clicked.connect(file_launch)
    return window

if __name__ == '__main__':
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
        created_app = True
    else:
        created_app = False
    launcher_window = launcher()
    launcher_window.show()
    launcher_window.raise_()
    launcher_window.activateWindow()
    if created_app == True:
        app.exec()



