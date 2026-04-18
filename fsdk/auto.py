# this code generates const.py module that contais constants defined in LuxandFaceSDK.h
### for internal use ###

import re

with open("LuxandFaceSDK.h") as f: source = f.read()

with open('const.py', 'w') as f:
	print("# auto generated file out of LuxandFaceSDK.h", file = f)

	# generate enum constants
	for body, desc in re.findall('typedef\s+enum\s+\{(.*?)\}\s*(\w*?)\s*;', source, re.DOTALL):
		print(f'\n### enum {desc.strip()}', file=f)
		for ind, name in enumerate(re.findall('FSDK_\w+', body)):
			print(f'{name} = {ind}', file=f)

	# generate error codes
	print('\n### Error codes', file=f)
	for name, value in re.findall('#define\s+(FSDKE_\w+)\s+(-??\d+)', source):
		print(f'{name} = {value}', file=f)

	# generate FSDK_FACIAL_FEATURE_COUNT
	fcount = re.findall('#define\s+FSDK_FACIAL_FEATURE_COUNT\s+(\d+)', source)[0]
	print(f'\n### Facial feature count\nFSDK_FACIAL_FEATURE_COUNT = {fcount}', file = f)

	# generate facial features
	print('\n### Facial features', file=f)
	for name, value in re.findall('#define\s+(FSDKP_\w+)\s+(\d+)', source):
		print(f'{name} = {value}', file=f)

	# generate FACE_TEMPLATE_SIZE
	magic = re.findall('\{[^{}]+?\[\s*(\d+)\s*\].+?\}\s*FSDK_FaceTemplate\s*;', source, re.DOTALL)[0]
	print(f'\n### FSDK_FaceTemplate size\nFSDK_FACE_TEMPLATE_SIZE = {magic}', file = f)


	left_eye = """(FSDKP_LEFT_EYE, FSDKP_LEFT_EYE_INNER_CORNER, FSDKP_LEFT_EYE_OUTER_CORNER,
	FSDKP_LEFT_EYE_LOWER_LINE1, FSDKP_LEFT_EYE_LOWER_LINE2, FSDKP_LEFT_EYE_LOWER_LINE3,
	FSDKP_LEFT_EYE_UPPER_LINE1, FSDKP_LEFT_EYE_UPPER_LINE2, FSDKP_LEFT_EYE_UPPER_LINE3,
	FSDKP_LEFT_EYE_RIGHT_IRIS_CORNER, FSDKP_LEFT_EYE_LEFT_IRIS_CORNER)"""
	right_eye = """(FSDKP_RIGHT_EYE, FSDKP_RIGHT_EYE_INNER_CORNER, FSDKP_RIGHT_EYE_OUTER_CORNER,
	FSDKP_RIGHT_EYE_LOWER_LINE1, FSDKP_RIGHT_EYE_LOWER_LINE2, FSDKP_RIGHT_EYE_LOWER_LINE3,
	FSDKP_RIGHT_EYE_UPPER_LINE1, FSDKP_RIGHT_EYE_UPPER_LINE2, FSDKP_RIGHT_EYE_UPPER_LINE3,
	FSDKP_RIGHT_EYE_LEFT_IRIS_CORNER, FSDKP_RIGHT_EYE_RIGHT_IRIS_CORNER)"""

	print('\n### Combinations', file = f)
	print('\nFSDKP_LEFT_EYE_SET = ', left_eye, file = f)
	print('\nFSDKP_RIGHT_EYE_SET = ', right_eye, file = f)
