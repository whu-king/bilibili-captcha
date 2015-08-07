# Manage all dataset

import os
import random
import json
import time
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import captcha_source
import config as c
from captcha_recognizer import CaptchaRecognizer

_cm_greys = plt.cm.get_cmap('Greys')
_png = '.png'

dataset_dir = c.get('dataset')
training_set_dir = os.path.join(dataset_dir, c.get('training'))
training_char_dir = os.path.join(dataset_dir, c.get('training_char'))
test_set_dir = os.path.join(dataset_dir, c.get('test'))

_PARTITION_JSON = os.path.join(dataset_dir, 'partition.json')
_NUM_TOTAL = '###total'
_NUM_FAIL = '##fail'
_NUM_SUCCESS = '##success'
_SUCCESS_RATE = '##success_rate'
_NUM_CHAR = '#{}'
_FAIL = 'fail'
_SUCCESS = 'success'


def _contain_invalid_char(seq):
    return any(char not in captcha_source.chars for char in seq)


def _get_training_char_dir(char):
    return os.path.join(training_char_dir, char)


def _make_all_char_dirs():
    for char in captcha_source.chars:
        c.make_dirs(_get_training_char_dir(char))


c.make_dirs(training_set_dir)
c.make_dirs(training_char_dir)
c.make_dirs(test_set_dir)
_make_all_char_dirs()


def char_path(char, path):
    return os.path.join(training_char_dir, char, path)


# Fetch some CAPTCHA images from a CAPTCHA source to a directory
def _fetch_captchas_to_dir(directory, num=1, use_https=False):
    plt.ion()
    plt.show()
    for i in range(num):
        img = captcha_source.fetch_image(use_https)
        plt.clf()
        plt.axis('off')
        plt.imshow(img)
        # http://stackoverflow.com/questions/12670101/matplotlib-ion-function
        # -fails-to-be-interactive
        # https://github.com/matplotlib/matplotlib/issues/1646/
        plt.show()
        plt.pause(1e-2)
        while True:
            seq = input('[{}] Enter the char sequence: '.format(i))
            # To skip a CAPTCHA.
            # Warning: skipping may reduce the quality of the training set.
            if seq == '0':
                break
            seq = captcha_source.canonicalize(seq)
            if (len(seq) != captcha_source.captcha_length or
                    _contain_invalid_char(seq)):
                print('Invalid sequence!')
            else:
                break
        if seq == '0':
            print('Skipped manually')
            continue
        path = os.path.join(directory, _add_suffix(seq))
        if not os.path.isfile(path):
            mpimg.imsave(path, img)
        else:
            print('Warning: char sequence already exists in dataset! Skipping')
    plt.ioff()


def clear_training_set():
    c.clear_dir(training_set_dir)


def clear_training_chars():
    for directory in os.listdir(training_char_dir):
        c.clear_dir(os.path.join(training_char_dir, directory))


def clear_test_set():
    c.clear_dir(test_set_dir)


# def clear_dataset():
#     clear_training_set()
#     clear_test_set()


def fetch_training_set(num=1, use_https=False):
    _fetch_captchas_to_dir(training_set_dir, num, use_https)


def fetch_test_set(num=1, use_https=False):
    _fetch_captchas_to_dir(test_set_dir, num, use_https)


# Get one image from a directory
def _get_image(directory, filename):
    image = mpimg.imread(os.path.join(directory, filename))
    # Discard alpha channel
    return image[:, :, 0:3]


# Get some images from a directory
def _get_images(directory, num=1):
    filenames = _list_png(directory)
    if num > len(filenames):
        num = len(filenames)
        print('Warning: requesting more images than stored, returning all '
              'available')
    else:
        random.shuffle(filenames)
    return [_get_image(directory, filenames[i]) for i in range(num)]


def _add_suffix(basename, suffix=_png):
    return '{}{}'.format(basename, suffix)


def _remove_suffix(filename):
    basename, ext = os.path.splitext(filename)
    return basename


def _get_suffix(filename):
    basename, ext = os.path.splitext(filename)
    return ext


def get_test_image(seq):
    return _get_image(test_set_dir, _add_suffix(seq))


def get_test_images(num=1):
    return _get_images(test_set_dir, num)


# Return a training image randomly if seq is None
def get_training_image(seq=None):
    if seq is None:
        return get_training_images(1)[0]
    else:
        return _get_image(training_set_dir, _add_suffix(seq))


def get_training_images(num=1):
    return _get_images(training_set_dir, num)


# List all png files in a directory
def _list_png(directory):
    def png_filter(filename):
        return _get_suffix(filename) == _png

    return list(filter(png_filter, os.listdir(directory)))


def _list_seq(directory):
    return list(map(_remove_suffix, _list_png(directory)))


def partition_training_images_to_chars(force_update=False):
    time_start = time.time()
    try:
        json_dict = json.load(open(_PARTITION_JSON))
    except ValueError as e:
        print('Warning: failed to load {}. Reconstructing...'.
              format(_PARTITION_JSON))
        json_dict = {}
        force_update = True
    if force_update:
        json_dict[_FAIL] = []
        json_dict[_SUCCESS] = []
        for char in captcha_source.chars:
            json_dict[_NUM_CHAR.format(char)] = 0
    seqs = _list_seq(training_set_dir)
    num_total = len(seqs)
    old_seq_set = set(json_dict[_FAIL] + json_dict[_SUCCESS])

    def seq_filter(s):
        return s not in old_seq_set

    seqs = list(filter(seq_filter, seqs))
    num_update = len(seqs)
    num_update_success = 0
    recognizer = CaptchaRecognizer()

    for n in range(num_update):
        seq = seqs[n]
        print('{}/{}: {}'.format(n, num_update, seq))
        img = get_training_image(seq)
        char_images = recognizer.partition(img)
        # If successful
        if char_images is not None:
            json_dict[_SUCCESS].append(seq)
            num_update_success += 1
            for i in range(len(char_images)):
                char = seq[i]
                json_dict[_NUM_CHAR.format(char)] += 1
                path = char_path(char, _add_suffix('{}.{}'.format(seq, i + 1)))
                mpimg.imsave(path, char_images[i], cmap=_cm_greys)
        else:
            json_dict[_FAIL].append(seq)

    num_total_success = len(json_dict[_SUCCESS])
    json_dict[_NUM_TOTAL] = num_total
    json_dict[_NUM_FAIL] = num_total - num_total_success
    json_dict[_NUM_SUCCESS] = num_total_success
    total_success_rate = num_total_success / num_total if num_total else 0
    json_dict[_SUCCESS_RATE] = '{:.3%}'.format(total_success_rate)
    json_dict[_FAIL].sort()
    json_dict[_SUCCESS].sort()
    json.dump(
        json_dict,
        open(_PARTITION_JSON, 'w'),
        sort_keys=True,
        indent=2
    )

    print('Update: {}'.format(num_update))
    print('Update success: {}'.format(num_update_success))
    if num_update:
        print('Update success rate is: {}'.format(
            num_update_success / num_update))

    print('Total: {}'.format(num_total))
    print('Total success: {}'.format(num_total_success))
    print('Total success rate is: {}'.format(total_success_rate))

    time_end = time.time()
    print('Elapsed time of partitioning training images: {}'.format(
        time_end - time_start))


if __name__ == '__main__':
    pass
