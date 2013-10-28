#ifndef _BRIAN_DYNAMIC_ARRAY_H
#define _BRIAN_DYNAMIC_ARRAY_H

#include<vector>

using namespace std;

/*
 * 2D Dynamic array class
 *
 * Efficiency note: if you are regularly resizing, make sure it is the first dimension that
 * is resized, not the second one.
 *
 */
template<class T>
class DynamicArray2D
{
	int old_n, old_m;
	vector< vector<T>* > data;
public:
	int n, m;
	DynamicArray2D(int _n=0, int _m=0)
	{
		old_n = 0;
		old_m = 0;
		resize(_n, _m);
	};
	~DynamicArray2D()
	{
		resize(0, 0); // handles deallocation
	}
	void resize()
	{
		if(old_n!=n)
		{
			if(n<old_n)
			{
				for(int i=n; i<old_n; i++)
				{
					if(data[i]) delete data[i];
					data[i] = 0;
				}
			}
			data.resize(n);
			if(n>old_n)
			{
				for(int i=old_n; i<n; i++)
				{
					data[i] = new vector<T>;
				}
			}
			if(old_m!=m)
			{
				for(int i=0; i<n; i++)
					data[i]->resize(m);
			} else if(n>old_n)
			{
				for(int i=old_n; i<n; i++)
					data[i]->resize(m);
			}
		} else if(old_m!=m)
		{
			for(int i=0; i<n; i++)
			{
				data[i]->resize(m);
			}
		}
		old_n = n;
		old_m = m;
	};
	void resize(int _n, int _m)
	{
		n = _n;
		m = _m;
		resize();
	}
	inline T& operator()(int i, int j)
	{
		return (*data[i])[j];
	}
};

#endif
