from os.path import exists
from array import array
from struct import unpack, pack
from random import randrange
from random import shuffle
from os import remove

import pyaudio
import wave

THRESHOLD = 500
NOISE_THRESHOLD = 500
CHUNK_SIZE = 1024
FORMAT = pyaudio.paInt16
MAX_INT_VAL_MAP = {pyaudio.paInt16: 2**15}
MAX_INT_VAL = MAX_INT_VAL_MAP[FORMAT]
RATE = 44100
WRITE_PERMUTATION = True
SILENCE_LENGTH = .0
MAX_PERMUTATIONS = 4


def is_silent(L):
    "Returns `True` if below the 'silent' threshold"
#    return max(L) < THRESHOLD
    return float(sum([abs(l) for l in L]))/len(L) < THRESHOLD

def addSoundInts(*args):
    if len(args) < 1:
        return 0
    elif len(args) < 2:
        return args[0]
    int_sum = args[0] + MAX_INT_VAL
    for i in range(1, len(args)):
        b = args[i] + MAX_INT_VAL
        if int_sum < MAX_INT_VAL and b < MAX_INT_VAL:
            int_sum = int_sum * b / MAX_INT_VAL
        else:
            int_sum = 2 * (int_sum + b) - int_sum * b / MAX_INT_VAL - 2 * MAX_INT_VAL

    return min(int_sum - MAX_INT_VAL, MAX_INT_VAL-1)

def normalize(L):
    "Average the volume out"
#    print len(L)
    if len(L) == 0:
        print "length L is 0"
        return L
    MAXIMUM = 16384
    times = float(MAXIMUM)/max(abs(i) for i in L)

    LRtn = array('h')
    for i in L:
        LRtn.append(int(i*times))
    return LRtn

def chunkNormalize(L):
    "Average the volume out"
#    print len(L)
    if len(L) == 0:
        print "length L is 0"
        return L
    MAXIMUM = 16384
    LRtn = array('h')
    for i in range(0, len(L), CHUNK_SIZE):
        chunk = L[i: i + CHUNK_SIZE]
        times = float(MAXIMUM)/max(abs(i) for i in chunk)

        for i in chunk:
            LRtn.append(min(int(i*times), MAXIMUM-1))
    return LRtn

def trim(L):
    "Trim the blank spots at the start and end"
    def _trim(L):
        snd_started = False
        LRtn = array('h')

        for i in range(0, len(L), CHUNK_SIZE/4):
            if not snd_started:
                chunk = L[i:i+CHUNK_SIZE/4]
                average = float(sum([abs(a) for a in chunk]))/len(chunk)
#                print str(i) + " " + str(average)
                if average > THRESHOLD:
                    snd_started = True
                    for j in chunk:
                        if j > NOISE_THRESHOLD:
                            LRtn.append(j)
                        else:
                            LRtn.append(0)

            elif snd_started:
                for j in chunk:
                    if j > NOISE_THRESHOLD:
                        LRtn.append(j)
                    else:
                        LRtn.append(0)
        return LRtn

    # Trim to the left
    L = _trim(L)

    # Trim to the right
    L.reverse()
    L = _trim(L)
    L.reverse()
    return L

def create_silence(seconds):
    return array('h', [0 for i in xrange(int(seconds*RATE))])

def add_silence(L, seconds):
    "Add silence to the start and end of `L` of length `seconds` (float)"
    LRtn = array('h', [0 for i in xrange(int(seconds*RATE))])
    LRtn.extend(L)
    LRtn.extend([0 for i in xrange(int(seconds*RATE))])
    return LRtn

def playback(L, sample_width):
    q = pyaudio.PyAudio()
    stream = q.open(format=q.get_format_from_width(sample_width), channels=1, rate=RATE,
            output=True, frames_per_buffer=CHUNK_SIZE)
    data = L[:CHUNK_SIZE]
    i = 0;
    while data:
        stream.write(data)
        i += CHUNK_SIZE
        data = L[i:i + CHUNK_SIZE]

def playWave(wf_name):
    wf = wave.open(wf_name, 'rb')
    
    p = pyaudio.PyAudio()

# open stream
    stream = p.open(format = p.get_format_from_width(wf.getsampwidth()),channels = wf.getnchannels(),rate = wf.getframerate(),output = True)

# read data
    data = wf.readframes(CHUNK_SIZE)

# play stream
    while data != '':
        stream.write(data)
        data = wf.readframes(CHUNK_SIZE)

    stream.close()
    p.terminate()

def record():
    """
    Record a word or words from the microphone and 
    return the data as an array of signed shorts.

    Normalizes the audio, trims silence from the 
    start and end, and pads with 0.5 seconds of 
    blank sound to make sure VLC et al can play 
    it without getting chopped off.
    """
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=1, rate=RATE, 
                    input=True, output=True,
                    frames_per_buffer=CHUNK_SIZE)

    num_silent = 0
    snd_started = False
    wrd_started = False

    LRtn = array('h')
    sound_list = []
    temp = array('h')

    while 1:
        data = stream.read(CHUNK_SIZE)
        L = unpack('<' + ('h'*(len(data)/2)), data) # little endian, signed short
        L = array('h', L)
        if wrd_started:
            LRtn.extend(L)

        silent = is_silent(L)
        print silent, num_silent, max(L), float(sum([abs(l) for l in L]))/len(L)

        if silent and snd_started:
            num_silent += 1
        elif not silent and not wrd_started:
            snd_started = True
            wrd_started = True
            LRtn.extend(temp)
            num_silent = 0
        if wrd_started and num_silent > 10:
            wrd_started = False
            sound_list.append(LRtn)
            LRtn = array('h')
        if snd_started and num_silent > 100:
            break
        temp = L

    sample_width = p.get_sample_size(FORMAT)
    
    stream.stop_stream()
    stream.close()
    p.terminate()
    new_sound_list = []
    for lsound in sound_list:
#        lsound = trim(lsound)
        lsound = normalize(lsound)
#        lsound = add_silence(lsound, 0.5)
        new_sound_list.append(lsound)
    return sample_width, new_sound_list

def record_to_file(path):
    "Records from the microphone and outputs the resulting data to `path`"
    sample_width, data = record()
    path = path.split(".")
    x = 1
    paths = []
    if WRITE_PERMUTATION:
        writePermutation(path, data, sample_width)
    for d in data:
#        playback(d, sample_width) 
        d = pack('<' + ('h'*len(d)), *d)
        wf_path = path[0] + str(x) + "." + path[1]
        wf = wave.open(wf_path, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(sample_width)
        wf.setframerate(RATE)
        wf.writeframes(d)
        wf.close()
        paths.append(wf_path)
#        playWave(path[0] + str(x) + "." + path[1])
        x += 1
    s = create_silence(SILENCE_LENGTH)
    s = pack('<' + ('h'*len(s)), *s)
    silence_path = 'silence.wav'
    wf = wave.open(silence_path, 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(sample_width)
    wf.setframerate(RATE)
    wf.writeframes(s)
    wf.close()
    return paths, silence_path

def blendData(split_data, path, sample_width):
    split_perms = []
    data_lengths = []
    perm_lengths = []

    for i in range(0, len(split_data)):
        data = split_data[i]
        data_lengths.append(sum([len(d) for d in data]))
        split_perms.append(permuteList(range(0, len(data)), True))
        perm_lengths.append(data_lengths[i]*len(split_perms[i]))
    
    wf_path = path[0] + "_layered." + path[1]
    wf = wave.open(wf_path, 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(sample_width)
    wf.setframerate(RATE)

    perm_index = [0 for a in split_perms]
    perm_data =  [0 for a in split_perms]
    index_in_perm =  [0 for a in split_perms]
    data_to_sum =  [0 for a in split_perms]
    write_buffer = array('h')
    for j in range(0, max(perm_lengths)):
        for k in range(0, len(split_perms)):
            index_in_perm[k] = j % data_lengths[k]
            if index_in_perm[k] == 0:
                perm_index[k] = (j / data_lengths[k]) % len(split_perms[k])
                perm_data[k] = array('h')
                for l in split_perms[k][perm_index[k]]:
                    perm_data[k].extend(split_data[k][l])
            data_to_sum[k] = perm_data[k][index_in_perm[k]]
        if min(index_in_perm) == 0:
            write_buffer = normalize(write_buffer)
            wf.writeframes(pack('<' + ('h'*len(write_buffer)), *write_buffer))
            write_buffer = array('h')
        write_buffer.append(addSoundInts(*data_to_sum))
    
    wf.writeframes(pack('<' + ('h'*len(write_buffer)), *write_buffer))
    wf.close()
    playWave(wf_path)
            

def writePermutation(path, data, sample_width):
    split_data = []
    for i in range(0, len(data), MAX_PERMUTATIONS):
        split_data.append(data[i: i+MAX_PERMUTATIONS])
    blendData(split_data, path, sample_width)

"""
    perms = permuteList(range(0, len(data)))
    
    wf_path = path[0] + "_permuted." + path[1]
    wf = wave.open(wf_path, 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(sample_width)
    wf.setframerate(RATE)
    while len(perms) > 0: 
        perm = perms.pop(randrange(0,len(perms)))
        for p in perm:
            d = pack('<' + ('h'*len(data[p])), *data[p])
            wf.writeframes(d)
        s = create_silence(SILENCE_LENGTH)
        s = pack('<' + ('h'*len(s)), *s)
        wf.writeframes(s)
    wf.close()
"""
def permuteList(input_list, shuffle_list=False):
    if len(input_list) == 1:
        return [input_list]
    else:
        perms = []
        for i in range(0, len(input_list)):
            sub_list = input_list[0:i] + input_list[i+1:]
            ret = permuteList(sub_list)
            for j in ret:
                perms.append([input_list[i]] + j)
        if shuffle_list:
            shuffle(perms)
        return perms

def playPermutations(paths, silence_path):
    perms = permuteList(paths)
    while len(perms) > 0:
        perm = perms.pop(randrange(0,len(perms)))
        for p in perm:
            playWave(p)
        playWave(silence_path)

def test():
    paths, silence_path = record_to_file('temp.wav')
#    playPermutations(paths, silence_path) 
    for path in paths:
        remove(path)   

if __name__ == '__main__':
    paths, silence_path = record_to_file('temp.wav')
#    playPermutations(paths, silence_path) 
    for path in paths:
        remove(path)
